import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

const ink = Color(0xFF071521);
const panel = Color(0xFF102432);
const border = Color(0xFF254351);
const mint = Color(0xFF65E7C7);
const pale = Color(0xFFEAF7F4);
const muted = Color(0xFF94ADB8);
const amber = Color(0xFFFFCC7C);
const defaultHost = String.fromEnvironment('ESP32_HOST');

void main() => runApp(
  const MaterialApp(debugShowCheckedModeBanner: false, home: SignalPage()),
);

class SignalPage extends StatefulWidget {
  const SignalPage({super.key});
  @override
  State<SignalPage> createState() => _SignalPageState();
}

class _SignalPageState extends State<SignalPage> {
  final host = TextEditingController(text: defaultHost);
  final samples = <double>[];
  WebSocketChannel? channel;
  StreamSubscription<dynamic>? subscription;
  Timer? retryTimer, watchdog, demoTimer;
  String status = 'Enter your ESP32 IP address to begin';
  String calibration = '—';
  bool connected = false, connecting = false, demo = false, wanted = false;
  int generation = 0, packets = 0, gaps = 0, drops = 0, rate = 0;
  int latestRaw = 0, latestMv = 0, minimum = 0, maximum = 0;
  int? priorSeq, priorDrops;
  double mean = 0, phase = 0;
  DateTime? lastPacket, lastPaint, connectedAt;
  int retryCount = 0;

  @override
  void initState() {
    super.initState();
    watchdog = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted || !wanted || demo || !connected) return;
      final reference = lastPacket ?? connectedAt;
      if (reference != null &&
          DateTime.now().difference(reference) > const Duration(seconds: 4)) {
        disconnect('Stream paused · reconnecting', retry: true);
      } else {
        setState(() {});
      }
    });
    if (defaultHost.isNotEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) => connect());
    }
  }

  @override
  void dispose() {
    wanted = false;
    retryTimer?.cancel();
    watchdog?.cancel();
    demoTimer?.cancel();
    subscription?.cancel();
    channel?.sink.close();
    host.dispose();
    super.dispose();
  }

  void connect() async {
    final address = host.text.trim();
    if (address.isEmpty) {
      setState(() => status = 'Enter the ESP32 IP address first');
      return;
    }
    demoTimer?.cancel();
    retryTimer?.cancel();
    subscription?.cancel();
    channel?.sink.close();
    final id = ++generation;
    wanted = true;
    demo = false;
    connected = false;
    connecting = true;
    lastPacket = null;
    connectedAt = null;
    setState(() => status = 'Connecting to ESP32…');
    try {
      final uri = Uri.parse(
        address.startsWith('ws://') || address.startsWith('wss://')
            ? address
            : 'ws://$address:81/',
      );
      final socket = WebSocketChannel.connect(uri);
      channel = socket;
      await socket.ready.timeout(const Duration(seconds: 7));
      if (!mounted || id != generation) return;
      setState(() {
        connected = true;
        connecting = false;
        connectedAt = DateTime.now();
        status = 'Connected · waiting for telemetry';
      });
      subscription = socket.stream.listen(
        (event) => receive(event, id),
        onError: (_) {
          if (id == generation) {
            disconnect('Connection lost · reconnecting', retry: true);
          }
        },
        onDone: () {
          if (id == generation) {
            disconnect('Connection closed · reconnecting', retry: true);
          }
        },
        cancelOnError: true,
      );
    } catch (_) {
      if (mounted && id == generation) {
        disconnect('ESP32 unavailable · retrying', retry: true);
      }
    }
  }

  void disconnect(String message, {bool retry = false}) {
    if (!mounted || demo || (retry && !wanted)) return;
    ++generation;
    subscription?.cancel();
    subscription = null;
    channel?.sink.close();
    channel = null;
    setState(() {
      connected = false;
      connecting = false;
      status = message;
    });
    retryTimer?.cancel();
    if (retry && wanted) {
      final seconds = math.min(2 << math.min(retryCount++, 2), 8);
      retryTimer = Timer(Duration(seconds: seconds), connect);
    }
  }

  void stop() {
    wanted = false;
    retryTimer?.cancel();
    demoTimer?.cancel();
    if (demo) {
      demo = false;
      ++generation;
      setState(() => status = 'Disconnected');
    } else {
      disconnect('Disconnected');
    }
  }

  void receive(dynamic event, int id) {
    if (!mounted || id != generation || event is! String) return;
    try {
      final packet = jsonDecode(event);
      if (packet is! Map<String, dynamic> || packet['v'] != 1) return;
      final raw = packet['raw'], millivolts = packet['mv'];
      if (raw is! List ||
          millivolts is! List ||
          raw.isEmpty ||
          raw.length != millivolts.length) {
        return;
      }
      final values = raw.map((e) => (e as num).toDouble()).toList();
      final seq = (packet['seq'] as num).toInt();
      final deviceDrops = (packet['dropped'] as num).toInt();
      if (priorSeq != null && seq > priorSeq! + 1) gaps += seq - priorSeq! - 1;
      if (priorDrops != null && deviceDrops >= priorDrops!) {
        drops += deviceDrops - priorDrops!;
      }
      priorSeq = seq;
      priorDrops = deviceDrops;
      rate = (packet['fs_hz'] as num).toInt();
      calibration = packet['calibration']?.toString() ?? 'unknown';
      latestRaw = values.last.round();
      latestMv = (millivolts.last as num).toInt();
      minimum = values.reduce(math.min).round();
      maximum = values.reduce(math.max).round();
      mean = values.reduce((a, b) => a + b) / values.length;
      samples.addAll(values);
      final limit = math.max(1024, rate * 2);
      if (samples.length > limit) {
        samples.removeRange(0, samples.length - limit);
      }
      packets++;
      lastPacket = DateTime.now();
      retryCount = 0;
      if (lastPaint == null ||
          DateTime.now().difference(lastPaint!) >
              const Duration(milliseconds: 90)) {
        lastPaint = DateTime.now();
        setState(() => status = 'Streaming live from ESP32');
      }
    } catch (_) {
      /* Ignore a malformed batch and await the next one. */
    }
  }

  void startDemo() {
    wanted = false;
    retryTimer?.cancel();
    subscription?.cancel();
    channel?.sink.close();
    ++generation;
    demo = true;
    connected = false;
    connecting = false;
    samples.clear();
    rate = 1000;
    calibration = 'simulated';
    demoTimer?.cancel();
    demoTimer = Timer.periodic(const Duration(milliseconds: 100), (_) {
      if (!mounted) return;
      for (var i = 0; i < 100; i++) {
        phase += 0.024;
        samples.add(1850 + 650 * math.sin(phase) + 110 * math.sin(phase * 4.2));
      }
      if (samples.length > 2000) samples.removeRange(0, samples.length - 2000);
      setState(() {
        latestRaw = samples.last.round();
        latestMv = (latestRaw * .8).round();
        minimum = samples.reduce(math.min).round();
        maximum = samples.reduce(math.max).round();
        mean = samples.reduce((a, b) => a + b) / samples.length;
        status = 'Simulation · no device data';
      });
    });
    setState(() => status = 'Simulation · no device data');
  }

  @override
  Widget build(BuildContext context) {
    final compact = MediaQuery.sizeOf(context).width < 900;
    return Scaffold(
      backgroundColor: ink,
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [ink, Color(0xFF0D2A32), ink],
          ),
        ),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: EdgeInsets.symmetric(
              horizontal: compact ? 18 : 44,
              vertical: 28,
            ),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 1400),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 38,
                          height: 38,
                          decoration: BoxDecoration(
                            color: mint,
                            borderRadius: BorderRadius.circular(11),
                          ),
                          child: const Icon(Icons.bolt_rounded, color: ink),
                        ),
                        const SizedBox(width: 12),
                        const Text(
                          'PHOTON',
                          style: TextStyle(
                            color: pale,
                            fontSize: 18,
                            fontWeight: FontWeight.w900,
                            letterSpacing: 3,
                          ),
                        ),
                        const Spacer(),
                        if (!compact)
                          const Text(
                            'SIGNAL LAB   /   ESP32',
                            style: TextStyle(
                              color: muted,
                              fontSize: 11,
                              letterSpacing: 1.5,
                            ),
                          ),
                        const SizedBox(width: 22),
                        pill(
                          demo
                              ? 'DEMO DATA'
                              : connected
                              ? 'LIVE DEVICE'
                              : connecting
                              ? 'CONNECTING'
                              : 'OFFLINE',
                          demo
                              ? amber
                              : connected
                              ? mint
                              : muted,
                        ),
                      ],
                    ),
                    const SizedBox(height: 40),
                    const Text(
                      'OPTICAL FRONT-END  /  LIVE TELEMETRY',
                      style: TextStyle(
                        color: mint,
                        fontSize: 11,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 2,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'See the signal.\nUnderstand the system.',
                      style: TextStyle(
                        color: pale,
                        fontSize: compact ? 36 : 54,
                        height: 1.08,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 14),
                    const Text(
                      'A real-time view of the ESP32 ADC stream, packet health and acquisition settings.',
                      style: TextStyle(color: muted, fontSize: 14),
                    ),
                    const SizedBox(height: 28),
                    connectionPanel(compact),
                    const SizedBox(height: 18),
                    notice(),
                    const SizedBox(height: 20),
                    compact
                        ? Column(
                            children: [
                              chart(),
                              const SizedBox(height: 16),
                              metrics(),
                            ],
                          )
                        : Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(flex: 7, child: chart()),
                              const SizedBox(width: 18),
                              Expanded(flex: 3, child: metrics()),
                            ],
                          ),
                    const SizedBox(height: 18),
                    health(),
                    const SizedBox(height: 28),
                    const Text(
                      'ESP32 DEV MODULE  /  ADC1 GPIO34  /  TELEMETRY v1',
                      style: TextStyle(
                        color: muted,
                        fontSize: 10,
                        letterSpacing: 1.5,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget box(Widget child) => Container(
    decoration: BoxDecoration(
      color: panel,
      border: Border.all(color: border),
      borderRadius: BorderRadius.circular(20),
    ),
    child: child,
  );
  Widget pill(String label, Color color) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
    decoration: BoxDecoration(
      color: color.withAlpha(25),
      border: Border.all(color: color.withAlpha(85)),
      borderRadius: BorderRadius.circular(30),
    ),
    child: Text(
      label,
      style: TextStyle(
        color: color,
        fontSize: 10,
        letterSpacing: 1,
        fontWeight: FontWeight.w800,
      ),
    ),
  );

  Widget connectionPanel(bool compact) {
    final label = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'DEVICE CONNECTION',
          style: TextStyle(
            color: muted,
            fontSize: 10,
            fontWeight: FontWeight.w800,
            letterSpacing: 1.5,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          status,
          style: TextStyle(
            color: connected
                ? mint
                : demo
                ? amber
                : pale,
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
    final input = SizedBox(
      height: 46,
      child: TextField(
        controller: host,
        style: const TextStyle(color: pale, fontSize: 14),
        onSubmitted: (_) => connect(),
        decoration: InputDecoration(
          hintText: 'ESP32 IP address',
          hintStyle: const TextStyle(color: muted),
          prefixIcon: const Icon(Icons.wifi_rounded, color: mint),
          filled: true,
          fillColor: ink,
          contentPadding: const EdgeInsets.symmetric(vertical: 11),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: border),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: border),
          ),
        ),
      ),
    );
    final buttons = Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        FilledButton.icon(
          onPressed: connected || connecting ? stop : connect,
          icon: Icon(
            connected || connecting ? Icons.stop_rounded : Icons.link_rounded,
            size: 18,
          ),
          label: Text(connected || connecting ? 'Stop' : 'Connect'),
          style: FilledButton.styleFrom(
            backgroundColor: mint,
            foregroundColor: ink,
            minimumSize: const Size(106, 46),
          ),
        ),
        OutlinedButton(
          onPressed: demo ? stop : startDemo,
          style: OutlinedButton.styleFrom(
            foregroundColor: pale,
            side: const BorderSide(color: border),
            minimumSize: const Size(106, 46),
          ),
          child: Text(demo ? 'Stop demo' : 'Try demo'),
        ),
      ],
    );
    return box(
      Padding(
        padding: const EdgeInsets.all(18),
        child: compact
            ? Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  label,
                  const SizedBox(height: 14),
                  input,
                  const SizedBox(height: 12),
                  buttons,
                ],
              )
            : Row(
                children: [
                  Expanded(flex: 3, child: label),
                  Expanded(flex: 3, child: input),
                  const SizedBox(width: 14),
                  buttons,
                ],
              ),
      ),
    );
  }

  Widget notice() => Container(
    padding: const EdgeInsets.all(15),
    decoration: BoxDecoration(
      color: amber.withAlpha(18),
      border: Border.all(color: amber.withAlpha(80)),
      borderRadius: BorderRadius.circular(14),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Icon(Icons.info_outline_rounded, color: amber, size: 19),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            demo
                ? 'SIMULATED DATA · This waveform is generated in the browser for interface demonstration only.'
                : 'ADC INPUT OPEN · GPIO34 is unconnected until the photodiode/TIA board is attached. Live readings are floating-pin diagnostics, not optical measurements.',
            style: const TextStyle(color: amber, fontSize: 12.5, height: 1.4),
          ),
        ),
      ],
    ),
  );

  Widget chart() => box(
    Padding(
      padding: const EdgeInsets.fromLTRB(22, 22, 22, 19),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text(
                'ADC WAVEFORM',
                style: TextStyle(
                  color: pale,
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1,
                ),
              ),
              const Spacer(),
              pill(
                demo
                    ? 'SIMULATED'
                    : connected
                    ? 'LIVE'
                    : 'NO SIGNAL',
                demo
                    ? amber
                    : connected
                    ? mint
                    : muted,
              ),
            ],
          ),
          const SizedBox(height: 7),
          const Text(
            'Raw counts · latest 2 seconds · 12-bit scale',
            style: TextStyle(color: muted, fontSize: 12),
          ),
          const SizedBox(height: 24),
          SizedBox(
            height: 285,
            width: double.infinity,
            child: samples.isEmpty
                ? const Center(
                    child: Text(
                      'Waiting for the first sample batch',
                      style: TextStyle(color: muted),
                    ),
                  )
                : CustomPaint(painter: WavePainter(List<double>.of(samples))),
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              const Icon(Icons.circle, color: mint, size: 9),
              const SizedBox(width: 8),
              Text(
                demo ? 'DEMO TRACE' : 'ADC1 / GPIO34',
                style: const TextStyle(
                  color: muted,
                  fontSize: 11,
                  letterSpacing: 1,
                ),
              ),
              const Spacer(),
              Text(
                rate == 0
                    ? '— kS/s'
                    : '${(rate / 1000).toStringAsFixed(1)} kS/s',
                style: const TextStyle(
                  color: mint,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ],
      ),
    ),
  );

  Widget metrics() => Column(
    children: [
      Row(
        children: [
          Expanded(
            child: metric(
              'LATEST RAW',
              samples.isEmpty ? '—' : '$latestRaw',
              'counts / 4095',
              Icons.sensors_rounded,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: metric(
              'PIN VOLTAGE',
              samples.isEmpty ? '—' : '$latestMv',
              'mV · calibrated',
              Icons.bolt_rounded,
            ),
          ),
        ],
      ),
      const SizedBox(height: 10),
      Row(
        children: [
          Expanded(
            child: metric(
              'BATCH RANGE',
              samples.isEmpty ? '—' : '$minimum–$maximum',
              'raw counts',
              Icons.swap_vert_rounded,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: metric(
              'MEAN RAW',
              samples.isEmpty ? '—' : mean.toStringAsFixed(0),
              'counts / batch',
              Icons.functions_rounded,
            ),
          ),
        ],
      ),
    ],
  );

  Widget metric(String title, String value, String unit, IconData icon) =>
      SizedBox(
        height: 205,
        child: box(
          Padding(
            padding: const EdgeInsets.all(15),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Icon(icon, color: mint, size: 22),
                Text(
                  title,
                  style: const TextStyle(
                    color: muted,
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                    letterSpacing: .7,
                  ),
                ),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    value,
                    style: const TextStyle(
                      color: pale,
                      fontSize: 28,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                Text(unit, style: const TextStyle(color: muted, fontSize: 11)),
              ],
            ),
          ),
        ),
      );

  Widget health() => box(
    Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'STREAM HEALTH',
            style: TextStyle(
              color: pale,
              fontSize: 13,
              fontWeight: FontWeight.w800,
              letterSpacing: 1.1,
            ),
          ),
          const SizedBox(height: 18),
          Wrap(
            spacing: 44,
            runSpacing: 18,
            children: [
              healthItem('PACKETS', '$packets'),
              healthItem('DEVICE DROPS', '$drops samples'),
              healthItem('SEQ GAPS', '$gaps packets'),
              healthItem('CALIBRATION', calibration),
              healthItem(
                'LAST UPDATE',
                lastPacket == null
                    ? '—'
                    : '${DateTime.now().difference(lastPacket!).inSeconds}s ago',
              ),
            ],
          ),
        ],
      ),
    ),
  );

  Widget healthItem(String title, String value) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        title,
        style: const TextStyle(
          color: muted,
          fontSize: 10,
          fontWeight: FontWeight.w800,
          letterSpacing: 1,
        ),
      ),
      const SizedBox(height: 6),
      Text(
        value,
        style: const TextStyle(
          color: pale,
          fontSize: 14,
          fontWeight: FontWeight.w700,
        ),
      ),
    ],
  );
}

class WavePainter extends CustomPainter {
  final List<double> values;
  WavePainter(this.values);
  @override
  void paint(Canvas canvas, Size size) {
    const left = 40.0, top = 10.0, bottom = 20.0;
    final width = size.width - left - 8, height = size.height - top - bottom;
    if (width <= 0 || height <= 0) return;
    final grid = Paint()
      ..color = border
      ..strokeWidth = 1;
    for (var i = 0; i <= 4; i++) {
      final y = top + height * i / 4;
      canvas.drawLine(Offset(left, y), Offset(size.width, y), grid);
      final label = TextPainter(
        text: TextSpan(
          text: '${(4095 * (4 - i) / 4).round()}',
          style: const TextStyle(color: muted, fontSize: 10),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      label.paint(canvas, Offset(0, y - 6));
    }
    for (var i = 0; i <= 6; i++) {
      final x = left + width * i / 6;
      canvas.drawLine(Offset(x, top), Offset(x, top + height), grid);
    }
    if (values.length < 2) return;
    final path = Path();
    final step = math.max(1, (values.length / math.max(1, width)).ceil());
    var first = true;
    for (var i = 0; i < values.length; i += step) {
      final x = left + width * i / (values.length - 1);
      final y = top + height * (1 - (values[i] / 4095).clamp(0, 1));
      if (first) {
        path.moveTo(x, y);
        first = false;
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = mint.withAlpha(38)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 8,
    );
    canvas.drawPath(
      path,
      Paint()
        ..color = mint
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.2,
    );
  }

  @override
  bool shouldRepaint(covariant WavePainter oldDelegate) => true;
}
