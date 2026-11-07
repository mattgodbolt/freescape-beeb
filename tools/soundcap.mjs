// The live disc's sound, as jsbeeb's SN76489 takes it (src/sound.6502):
// every byte the chip takes, by the vertical sync's tick it came in, and
// each sound asked for, at the tick before which it was asked. For
// tools/soundcheck.mjs and tools/livecheck.mjs, which hand the log to
// tools/mksound.py --check, the driver's model.
//
//   const cap = soundCapture(session, sym);   // before the disc boots
//   ... run ...
//   cap.log()  -> { init, ticks, asks }
//
// init: the bytes sound_init wrote; ticks[t]: the bytes the chip took from
// snd_tick's t-th call (counted from sound_init's) to the next; asks: each
// [t, sound], t the ticks begun when snd_ask put it in snd_next (or the
// harness did: cap.ask). Each tick's cycles, snd_tick's call to its
// return, by whether it found a sound playing.
export function soundCapture(session, sym) {
    const tm = session._machine;
    const cpu = tm.processor;
    const chip = session._soundChip;
    const SOUND_INIT = sym("sound_init"), BANK_DATA = sym("BANK_DATA");
    const SND_TICK = sym("snd_tick"), TICKED = sym("irq_handler.ticked"), ASKED = sym("snd_ask.asked");
    const SND_NEXT = sym("snd_next"), SND_PTR = sym("snd_ptr"), SND_LEFT = sym("snd_left");
    const ram = cpu.ramRomOs;
    let sink = null; // where the chip's bytes go: none before sound_init
    const cap = { init: null, ticks: [], asks: [] };
    const cycles = { idle: [], playing: [] };
    let from = null, playing = false;
    const take = chip.poke.bind(chip);
    chip.poke = (v) => {
        if (sink) sink.push(v);
        take(v);
    };
    const busy = () => ram[SND_NEXT] !== 0 || ram[SND_PTR + 1] !== 0 || ram[SND_LEFT] !== 0;
    cpu.debugInstruction.add((addr) => {
        if (addr === SND_TICK && cap.init) {
            sink = [];
            cap.ticks.push(sink);
            from = tm.elapsedCycles;
            playing = busy();
        } else if (addr === TICKED && from !== null) {
            (playing ? cycles.playing : cycles.idle).push(tm.elapsedCycles - from);
            from = null;
        } else if (addr === ASKED && cap.init) {
            cap.asks.push([cap.ticks.length, cpu.a]);
        } else if (addr === SOUND_INIT && (cpu.romsel & 15) === BANK_DATA && cpu.isBankPagedAt(BANK_DATA, addr)) {
            cap.init = sink = [];
        }
    });
    return {
        // the harness's own ask, as snd_ask's (snd_next free)
        ask(n) {
            if (ram[SND_NEXT] !== 0) throw new Error("snd_next isn't free");
            cap.asks.push([cap.ticks.length, n]);
            ram[SND_NEXT] = n;
        },
        busy,
        free: () => ram[SND_NEXT] === 0,
        ticks: () => cap.ticks.length,
        cycles,
        log: () => ({ init: cap.init ?? [], ticks: cap.ticks, asks: cap.asks }),
    };
}
