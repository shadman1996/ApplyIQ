/**
 * ==========================================================================
 * J.A.R.V.I.S. PROCEDURAL AUDIO & SPEECH SYNTHESIS ENGINE
 * Web Audio API Oscillators + Web Speech Synthesis
 * ==========================================================================
 */

class JarvisAudioEngine {
    constructor() {
        this.ctx = null;
        this.muted = false;
        this.synth = window.speechSynthesis || null;
        this.voice = null;
        this.initAudioContext();
        this.initVoice();
    }

    initAudioContext() {
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.ctx = new AudioContext();
        } catch (e) {
            console.warn("[JARVIS Audio] Web Audio API not supported", e);
        }
    }

    initVoice() {
        if (!this.synth) return;
        const setVoice = () => {
            const voices = this.synth.getVoices();
            // Look for a British or sleek Google voice (classic Jarvis vibe)
            this.voice = voices.find(v => v.lang.includes("en-GB") || v.name.includes("Male") || v.name.includes("UK")) 
                         || voices.find(v => v.lang.includes("en-US")) 
                         || voices[0];
        };

        setVoice();
        if (this.synth.onvoiceschanged !== undefined) {
            this.synth.onvoiceschanged = setVoice;
        }
    }

    ensureContext() {
        if (this.ctx && this.ctx.state === "suspended") {
            this.ctx.resume();
        }
    }

    // High-tech holographic button click tone
    playClick() {
        if (this.muted || !this.ctx) return;
        this.ensureContext();

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = "sine";
        osc.frequency.setValueAtTime(1200, this.ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(800, this.ctx.currentTime + 0.05);

        gain.gain.setValueAtTime(0.15, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + 0.05);

        osc.connect(gain);
        gain.connect(this.ctx.destination);

        osc.start();
        osc.stop(this.ctx.currentTime + 0.05);
    }

    // Power-up tone (Recon & Scan launch)
    playPowerUp() {
        if (this.muted || !this.ctx) return;
        this.ensureContext();

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(300, this.ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(1800, this.ctx.currentTime + 0.35);

        gain.gain.setValueAtTime(0.08, this.ctx.currentTime);
        gain.gain.linearRampToValueAtTime(0.15, this.ctx.currentTime + 0.2);
        gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.35);

        osc.connect(gain);
        gain.connect(this.ctx.destination);

        osc.start();
        osc.stop(this.ctx.currentTime + 0.35);
    }

    // Target locked / Confirmation chirp
    playSuccess() {
        if (this.muted || !this.ctx) return;
        this.ensureContext();

        const now = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = "sine";
        osc.frequency.setValueAtTime(880, now);
        osc.frequency.setValueAtTime(1320, now + 0.08);

        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.22);

        osc.connect(gain);
        gain.connect(this.ctx.destination);

        osc.start();
        osc.stop(now + 0.22);
    }

    // J.A.R.V.I.S. Speech Synthesis
    speak(text) {
        if (this.muted || !this.synth) return;
        this.synth.cancel(); // cancel any active queue

        const utter = new SpeechSynthesisUtterance(text);
        if (this.voice) utter.voice = this.voice;
        utter.rate = 1.05;
        utter.pitch = 0.95; // slightly deeper AI timbre
        utter.volume = 0.9;
        this.synth.speak(utter);
    }

    toggleMute() {
        this.muted = !this.muted;
        if (this.muted && this.synth) {
            this.synth.cancel();
        }
        return this.muted;
    }
}

window.jarvisAudio = new JarvisAudioEngine();
