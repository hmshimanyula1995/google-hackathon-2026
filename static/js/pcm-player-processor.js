/**
 * PCM Audio Player — AudioWorkletProcessor
 * Plays 24kHz 16-bit PCM audio from Gemini Live API.
 * Handles instant buffer clearing on interruption.
 */
class PCMPlayerProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        // Ring buffer: 180 seconds at 24kHz
        this.bufferSize = 24000 * 180;
        this.buffer = new Float32Array(this.bufferSize);
        this.writeIndex = 0;
        this.readIndex = 0;

        this.port.onmessage = (event) => {
            if (event.data.command === "endOfAudio") {
                // INSTANT buffer clear on interruption
                this.writeIndex = 0;
                this.readIndex = 0;
                return;
            }

            // Receive Int16 PCM data, convert to Float32
            const int16Data = new Int16Array(event.data);
            for (let i = 0; i < int16Data.length; i++) {
                this.buffer[this.writeIndex] = int16Data[i] / 32768.0;
                this.writeIndex = (this.writeIndex + 1) % this.bufferSize;
            }
        };
    }

    process(inputs, outputs) {
        const output = outputs[0][0];
        for (let i = 0; i < output.length; i++) {
            if (this.readIndex !== this.writeIndex) {
                output[i] = this.buffer[this.readIndex];
                this.readIndex = (this.readIndex + 1) % this.bufferSize;
            } else {
                output[i] = 0; // Silence when buffer is empty
            }
        }
        return true;
    }
}

registerProcessor("pcm-player-processor", PCMPlayerProcessor);
