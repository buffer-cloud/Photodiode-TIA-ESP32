import asyncio
import json
import numpy as np
import pytest
import websockets
from photodiode_tia import analysis, protocol, recorder, sessions
from photodiode_tia.calibration import CalibrationTable, CalibrationError
from photodiode_tia.client import TelemetryClient
from photodiode_tia.mock_server import make_synthetic_packet, SyntheticSignalConfig
from photodiode_tia.dashboard import RollingWindow, run_dashboard


def packet(seq=0, t=0):
    return make_synthetic_packet(seq, t, SyntheticSignalConfig(freq_hz=62.5, noise_std_mv=0), rng=np.random.default_rng(1))


def test_protocol_rejects_bad_arrays_and_boolean_version():
    for key, value in [("v", True), ("mv", [float("nan")]), ("dt_us", [0, 0]), ("raw", [4096])]:
        p = packet(); p[key] = value
        with pytest.raises(protocol.ProtocolError): protocol.parse_batch(p)


def test_fft_and_timing():
    batches = [protocol.parse_batch(packet(i, i*64000)) for i in range(8)]
    ts = analysis.assemble_epoch(batches)
    result = analysis.fft_spectrum(ts.t_us, ts.y, 4000)
    assert result.dominant_freq_hz == pytest.approx(62.5)
    assert max(result.amplitude) == pytest.approx(50, rel=.001)
    for times in [np.r_[ts.t_us[:100], ts.t_us[100:]+5000], ts.t_us + np.arange(ts.n)%2*100]:
        with pytest.raises(analysis.AnalysisError): analysis.fft_spectrum(times, ts.y, 4000)
    with pytest.raises(analysis.AnalysisError): analysis.assemble_epoch([batches[1], batches[0]])
    with pytest.raises(analysis.AnalysisError): analysis.assemble_epoch([batches[0], batches[2]])


def test_reboot_and_session(tmp_path):
    window = RollingWindow(2)
    rec = recorder.SessionRecorder(root=tmp_path)
    state = protocol.INITIAL_EPOCH_STATE
    for b in [protocol.parse_batch(packet(1, 64000)), protocol.parse_batch(packet())]:
        state, event = protocol.classify_batch(state, b)
        window.add_batch(b, event); rec.write_batch(b, event)
    path = rec.close()
    epochs, meta = sessions.load_session(path)
    assert len(epochs) == 2 and len(window.mv) == 256
    assert meta['synthetic'] is True
    assert 'dropped' in recorder.read_session_csv(path)


def test_calibration():
    table = CalibrationTable(np.array([250., 2400.]), np.array([260., 2390.]), 'mv')
    assert table.correct([1325])[0] == 1325
    assert np.isnan(table.correct([100])[0])
    with pytest.raises(CalibrationError): CalibrationTable(np.array([0., np.nan]), np.array([0., 1.]), 'mv')


def test_websocket():
    async def exercise():
        async def handler(ws):
            await ws.send('bad json')
            await ws.send(json.dumps(packet()))
            await asyncio.sleep(.05)
        async with websockets.serve(handler, '127.0.0.1', 0) as server:
            port = server.sockets[0].getsockname()[1]
            client = TelemetryClient(f'ws://127.0.0.1:{port}/')
            async for batch, event in client.stream():
                assert batch.n == 256 and client.stats.parse_errors == 1
                client.stop(); break
    asyncio.run(exercise())


def test_dashboard_headless(tmp_path):
    import matplotlib
    matplotlib.use('Agg', force=True)
    path = tmp_path/'dashboard.png'
    run_dashboard('127.0.0.1', port=1, duration_s=.1, save_snapshot=str(path), frame_interval_s=.02)
    assert path.stat().st_size > 10000


def test_mock_to_csv_to_fft(tmp_path):
    from photodiode_tia.mock_server import MockTelemetryServer
    async def exercise():
        mock = MockTelemetryServer(config=SyntheticSignalConfig(freq_hz=62.5, noise_std_mv=0), max_batches=8)
        rec = recorder.SessionRecorder(root=tmp_path)
        async with websockets.serve(mock._handler, '127.0.0.1', 0) as server:
            port = server.sockets[0].getsockname()[1]
            client = TelemetryClient(f'ws://127.0.0.1:{port}/')
            async for batch, event in client.stream():
                rec.write_batch(batch, event)
                if client.stats.batches_received == 8:
                    client.stop(); break
        epochs, metadata = sessions.load_session(rec.close())
        assert metadata['synthetic'] is True
        assert epochs[0].n == 2048
        fft = analysis.fft_spectrum(epochs[0].t_us, epochs[0].mv, epochs[0].fs_hz)
        assert fft.dominant_freq_hz == pytest.approx(62.5)
        assert fft.amplitude.max() == pytest.approx(50, rel=.001)
    asyncio.run(exercise())
