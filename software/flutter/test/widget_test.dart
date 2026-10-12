import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:photodiode_tia_viewer/main.dart';

void main() {
  testWidgets('dashboard identifies the open ADC and demo data', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: SignalPage()));
    expect(find.textContaining('ADC INPUT OPEN'), findsOneWidget);
    await tester.tap(find.text('Try demo'));
    await tester.pump();
    expect(find.textContaining('SIMULATED DATA'), findsOneWidget);
  });
}
