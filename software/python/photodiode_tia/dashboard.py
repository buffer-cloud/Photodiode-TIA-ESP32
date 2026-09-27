"""Live dashboard: `python -m photodiode_tia.dashboard --host <ip> [--record] [--window s]`.

Runs the asyncio WebSocket client in a background thread, feeding a
thread-safe queue; the main thread drains the queue and redraws matplotlib
each frame, so a slow plot never blocks receiving packets and a slow/looping
network never blocks the plot. Recording (if --record) is done by the
background thread as batches arrive, independent of the redraw cadence.

Labelling: everything drawn here is MEASURED if --host is real hardware, or
SYNTHETIC if pointed at mock_server.py -- this module does not know or care
which; label the source, not this code, when you cite a screenshot.
"""

from __future__ import annotations

import argparse
import logging
import queue
import threading
import time
from collections import deque
from typing import Optional, Tuple

import matplotlib

import numpy as np

from . import analysis, client, protocol, recorder
from .calibration import CalibrationTable
from .plotting import PALETTE, style_axes

logger = logging.getLogger(__name__)


class _ReceiverThread(threading.Thread):
    """Runs the asyncio client loop, pushing (batch, event) onto a queue."""

    def __init__(self, uri: str, out_queue: "queue.Queue", *, record: bool, notes: str = ""):
        super().__init__(daemon=True, name="telemetry-receiver")
        self.uri = uri
        self.out_queue = out_queue
        self.record = record
        self.notes = notes
        self._stop_event = threading.Event()
        self.client: Optional[client.TelemetryClient] = None
        self.session_dir = None
        self.loop = None
        self.task = None
        self.error: Optional[BaseException] = None

    def run(self) -> None:
        import asyncio

        async def _main():
            self.loop = asyncio.get_running_loop()
            self.task = asyncio.current_task()
            self.client = client.TelemetryClient(self.uri, on_error=lambda e, ctx: logger.warning("%s: %s", ctx, e))
            rec = recorder.SessionRecorder(notes=self.notes) if self.record else None
            try:
                async for batch, event in self.client.stream():
                    if rec is not None:
                        rec.write_batch(batch, event)
                    try:
                        self.out_queue.put_nowait((batch, event))
                    except queue.Full:
                        # The next displayed batch is classified against the last displayed one.
                        logger.warning("Dashboard queue full; display samples omitted; recorder retained packet")
                    if self._stop_event.is_set():
                        break
            finally:
                if rec is not None:
                    self.session_dir = rec.close()

        try:
            asyncio.run(_main())
        except asyncio.CancelledError:
            pass
        except BaseException as exc:  # surfaced to main thread via .error
            self.error = exc

    def stop(self) -> None:
        self._stop_event.set()
        if self.loop is not None and self.task is not None and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.task.cancel)


class RollingWindow:
    """Holds the most recent `window_s` seconds of a single epoch's samples."""

    def __init__(self, window_s: float):
        self.window_s = window_s
        self.epoch: Optional[int] = None
        self.t_us: deque = deque()
        self.raw: deque = deque()
        self.mv: deque = deque()
        self.fs_nominal_hz: float = 4000.0
        self.dropped_total = 0
        self.seq_gaps_total = 0
        self.gain_ohm = None
        self.provenance = "No data"
        self.quality_warning = ""
        self._state = protocol.INITIAL_EPOCH_STATE

    def add_batch(self, batch: protocol.Batch, event: protocol.BatchEvent) -> None:
        self._state, display_event = protocol.classify_batch(self._state, batch)
        event = display_event
        discontinuous = (event.new_epoch or event.seq_gap or event.seq_reordered or event.dropped_delta != 0
                         or (self.gain_ohm is not None and (self.gain_ohm != batch.gain_ohm or self.fs_nominal_hz != batch.fs_hz)))
        if discontinuous:
            logger.info("device epoch changed (%s -> %s); resetting dashboard window", self.epoch, event.epoch)
            self.t_us.clear()
            self.raw.clear()
            self.mv.clear()
        self.quality_warning = "; ".join(event.reasons) if discontinuous else ""
        self.provenance = batch.calibration or "Firmware calibration provenance unavailable"
        self.gain_ohm = batch.gain_ohm
        self.epoch = event.epoch
        self.fs_nominal_hz = batch.fs_hz
        self.dropped_total = batch.dropped
        self.seq_gaps_total += event.seq_gap

        for dt, r, m in zip(batch.dt_us, batch.raw, batch.mv):
            self.t_us.append(batch.t0_us + dt)
            self.raw.append(r)
            self.mv.append(m)

        if self.t_us:
            cutoff = self.t_us[-1] - int(self.window_s * 1e6)
            while len(self.t_us) > 1 and self.t_us[0] < cutoff:
                self.t_us.popleft()
                self.raw.popleft()
                self.mv.popleft()

    def as_arrays(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        return (
            np.array(self.t_us, dtype=np.float64),
            np.array(self.raw, dtype=np.float64),
            np.array(self.mv, dtype=np.float64),
        )


def _format_stats_text(window: RollingWindow) -> str:
    t_us, raw, mv = window.as_arrays()
    lines = [window.provenance, window.quality_warning, f"epoch: {window.epoch}", f"samples in window: {len(mv)}"]
    if mv.size >= 2:
        stats = analysis.time_domain_stats(mv)
        lines += [
            f"mean: {stats.mean:.2f} mV",
            f"rms: {stats.rms:.2f} mV",
            f"ac-rms (std): {stats.ac_rms:.3f} mV",
            f"peak-to-peak: {stats.peak_to_peak:.2f} mV",
        ]
        try:
            fft_res = analysis.fft_spectrum((t_us - t_us[0]).astype(np.int64), mv, window.fs_nominal_hz)
            lines.append(f"dominant freq: {fft_res.dominant_freq_hz:.2f} Hz")
            try:
                noise = analysis.noise_summary(mv, fft_res)
                lines.append(
                    f"band RMS (0-{noise.band_hz[1]:.0f} Hz): {noise.band_noise_rms:.3f} mV"
                )
            except analysis.AnalysisError as exc:
                lines.append(f"noise: n/a ({exc})")
        except analysis.AnalysisError as exc:
            lines.append(f"FFT: n/a ({exc})")
    else:
        lines.append("not enough samples yet")
    lines.append(f"dropped (cumulative): {window.dropped_total}")
    lines.append(f"seq gaps (cumulative): {window.seq_gaps_total}")
    return "\n".join(lines)


def run_dashboard(
    host: str,
    *,
    port: int = client.DEFAULT_PORT,
    window_s: float = 2.0,
    record: bool = False,
    duration_s: Optional[float] = None,
    save_snapshot: Optional[str] = None,
    frame_interval_s: float = 0.2,
    calibration_csv: Optional[str] = None,
) -> None:
    import matplotlib.pyplot as plt

    if window_s <= 0 or frame_interval_s <= 0:
        raise ValueError("window and frame interval must be positive")
    correction = CalibrationTable.from_csv(calibration_csv) if calibration_csv else None
    uri = client.default_uri(host, port)
    q: "queue.Queue" = queue.Queue(maxsize=64)
    receiver = _ReceiverThread(uri, q, record=record, notes=f"dashboard session, uri={uri}")
    receiver.start()

    window = RollingWindow(window_s)
    interactive = matplotlib.get_backend().lower() not in ("agg", "pdf", "svg", "ps", "template")

    fig, ((ax_raw, ax_mv), (ax_fft, ax_text)) = plt.subplots(2, 2, figsize=(11, 7))
    fig.suptitle(f"Photodiode TIA dashboard -- {uri}")
    (line_raw,) = ax_raw.plot([], [], lw=0.8)
    ax_raw.set_title("raw counts")
    ax_raw.set_xlabel("t (s, relative)")
    ax_raw.set_ylabel("counts")
    (line_mv,) = ax_mv.plot([], [], lw=0.8, color="tab:orange")
    ax_mv.set_title("mV (ADC-pin voltage; not ideal counts->volts)")
    ax_mv.set_xlabel("t (s, relative)")
    ax_mv.set_ylabel("mV")
    (line_fft,) = ax_fft.plot([], [], lw=0.8, color="tab:green")
    ax_fft.set_title("FFT amplitude (Hann window)")
    ax_fft.set_xlabel("Hz")
    ax_fft.set_ylabel("mV")
    ax_text.axis("off")
    text_artist = ax_text.text(0.02, 0.98, "", va="top", ha="left", family="monospace", fontsize=9)

    from matplotlib.widgets import Button, TextBox
    fig.subplots_adjust(bottom=0.23, hspace=0.4)
    running = [True]
    saved = [None]
    captured = deque(maxlen=1024)
    def connect(_):
        nonlocal receiver
        if not receiver.is_alive():
            window.t_us.clear(); window.raw.clear(); window.mv.clear(); captured.clear()
            receiver = _ReceiverThread(uri, q, record=record)
            receiver.start()
    def disconnect(_):
        receiver.stop()
        receiver.join(timeout=2)
    def clear(_):
        window.t_us.clear(); window.raw.clear(); window.mv.clear(); captured.clear()
    def save(_):
        rec = recorder.SessionRecorder(notes="Dashboard buffered snapshot; original telemetry mv",
            calibration_provenance=correction.provenance if correction else "firmware baseline")
        for b, e in captured:
            rec.write_batch(b, e)
        saved[0] = str(rec.close())
        logger.info("Saved %s", saved[0])
    def set_window(value):
        try:
            seconds = float(value)
            if 0 < seconds <= 60:
                window.window_s = seconds
        except ValueError:
            pass
    buttons = []
    for i, (label, callback) in enumerate([("Connect", connect), ("Disconnect", disconnect),
            ("Start", lambda _: running.__setitem__(0, True)),
            ("Stop", lambda _: running.__setitem__(0, False)), ("Save", save), ("Clear", clear)]):
        button = Button(fig.add_axes([0.06 + i * 0.15, 0.04, 0.13, 0.04]), label)
        button.on_clicked(callback); buttons.append(button)
    window_box = TextBox(fig.add_axes([0.15, 0.12, 0.12, 0.035]), "Window (s) ", initial=str(window_s))
    window_box.on_submit(set_window)
    t_start = time.monotonic()
    try:
        while plt.fignum_exists(fig.number) and (duration_s is None or (time.monotonic() - t_start) < duration_s):
            drained = False
            try:
                while True:
                    batch, event = q.get_nowait()
                    if running[0]:
                        captured.append((batch, event))
                        if correction is not None:
                            from dataclasses import replace
                            values = batch.mv if correction.x_mode == "mv" else batch.raw
                            batch = replace(batch, mv=tuple(correction.correct(values)),
                                            calibration=correction.provenance)
                        window.add_batch(batch, event)
                    drained = True
            except queue.Empty:
                pass

            if receiver.error is not None:
                logger.error("receiver thread failed: %s", receiver.error)
                break

            t_us, raw, mv = window.as_arrays()
            line_fft.set_data([], [])
            if t_us.size:
                t_rel_s = (t_us - t_us[0]) / 1e6
                line_raw.set_data(t_rel_s, raw)
                ax_raw.relim()
                ax_raw.autoscale_view()
                line_mv.set_data(t_rel_s, mv)
                ax_mv.relim()
                ax_mv.autoscale_view()
                if mv.size >= 16:
                    try:
                        fft_res = analysis.fft_spectrum(
                            (t_us - t_us[0]).astype(np.int64), mv, window.fs_nominal_hz
                        )
                        line_fft.set_data(fft_res.freqs_hz, fft_res.amplitude)
                        ax_fft.relim()
                        ax_fft.autoscale_view()
                    except analysis.AnalysisError:
                        line_fft.set_data([], [])

            else:
                line_raw.set_data([], []); line_mv.set_data([], []); line_fft.set_data([], [])
            try:
                text_artist.set_text(_format_stats_text(window))
            except analysis.AnalysisError as exc:
                line_fft.set_data([], [])
                text_artist.set_text(str(exc) + "\nCalibration outside measured range?")

            fig.canvas.draw_idle()
            if interactive:
                plt.pause(frame_interval_s)
            else:
                fig.canvas.flush_events()
                time.sleep(frame_interval_s)

            if not drained and not interactive and duration_s is None:
                # Non-interactive backend with no data and no duration limit: avoid a tight busy loop.
                time.sleep(frame_interval_s)
    finally:
        if save_snapshot:
            fig.savefig(save_snapshot)
            logger.info("saved dashboard snapshot to %s", save_snapshot)
        receiver.stop()
        receiver.join(timeout=5.0)
        if receiver.session_dir is not None:
            logger.info("recorded session to %s", receiver.session_dir)
        plt.close(fig)


def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live photodiode TIA telemetry dashboard.")
    p.add_argument("--calibration-csv", help="Measured DMM correction table")
    p.add_argument("--host", required=True, help="ESP32 IP/hostname, or mock_server.py host")
    p.add_argument("--port", type=int, default=client.DEFAULT_PORT)
    p.add_argument("--window", type=float, default=2.0, dest="window_s", help="rolling window, seconds")
    p.add_argument("--record", action="store_true", help="write a session CSV+metadata under software/python/sessions/")
    p.add_argument("--duration", type=float, default=None, dest="duration_s", help="stop after N seconds (for smoke tests/CI)")
    p.add_argument("--save-snapshot", default=None, help="save a final PNG snapshot to this path on exit")
    p.add_argument("--frame-interval", type=float, default=0.2, dest="frame_interval_s")
    return p.parse_args(argv)


def main(argv=None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    args = _parse_args(argv)
    run_dashboard(
        args.host,
        port=args.port,
        window_s=args.window_s,
        record=args.record,
        duration_s=args.duration_s,
        save_snapshot=args.save_snapshot,
        frame_interval_s=args.frame_interval_s,
        calibration_csv=args.calibration_csv,
    )


if __name__ == "__main__":
    main()
