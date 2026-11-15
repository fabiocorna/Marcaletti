// PROTOTYPE - NOT FOR PRODUCTION
// Question: La luce che si consuma e si ricarica solo alle fiamme trasforma un platform rilassato in percorsi da ragionare?
// Date: 2026-11-15
// Every tuning value lives here, each with value, min, max and step. The game reads them live
// through tune.<name> (index.html); the tweak panel, an add-on, writes them back here.
window.CONFIG = {
  seed: 1, // every gameplay random call reads rng(), seeded from this (or ?seed= in the address)
  light_per_jump: { value: 11, min: 0, max: 30, step: 1 },      // light spent by each jump (of light_max)
  light_per_tile: { value: 0.6, min: 0, max: 2, step: 0.05 },   // light spent per tile walked or flown sideways
  light_max: { value: 100, min: 40, max: 200, step: 5 },        // a full lantern
  view_min: { value: 70, min: 30, max: 200, step: 5 },          // px of sight with an almost empty lantern
  view_max: { value: 330, min: 150, max: 600, step: 10 },       // px of sight with a full lantern
  speed: { value: 5.5, min: 2, max: 10, step: 0.25 },           // tiles per second, walking
  accel: { value: 40, min: 5, max: 120, step: 1 },              // tiles per second², start and stop
  jump_height: { value: 3.8, min: 2, max: 6, step: 0.1 },       // tiles, holding the button
  gravity: { value: 52, min: 20, max: 120, step: 1 },           // tiles per second², rising
  fall_mult: { value: 1.6, min: 1, max: 3, step: 0.05 },        // gravity multiplier when falling
  jump_cut: { value: 0.45, min: 0.1, max: 1, step: 0.05 },      // rise kept when the button is let go early
  coyote: { value: 0.1, min: 0, max: 0.3, step: 0.01 },         // seconds a jump still counts after leaving a ledge
  jump_buffer: { value: 0.12, min: 0, max: 0.3, step: 0.01 },   // seconds a press before landing still jumps
  respawn_delay: { value: 0.6, min: 0.1, max: 2, step: 0.05 },  // seconds from death to the checkpoint
  volume: { value: 0.5, min: 0, max: 1, step: 0.05 },
};
