#pragma once

namespace console {

// Call once from setup().
void begin();

// Call every loop() iteration. Non-blocking: reads whatever is currently
// available on Serial and executes a command once a full line arrives.
void poll();

} // namespace console
