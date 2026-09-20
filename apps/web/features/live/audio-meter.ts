export type AudioMeterStop = () => void;

export function createAudioMeter(
  stream: MediaStream,
  onLevel: (level: number) => void,
): AudioMeterStop {
  const AudioContextClass = window.AudioContext;
  const context = new AudioContextClass();
  const source = context.createMediaStreamSource(stream);
  const analyser = context.createAnalyser();
  analyser.fftSize = 512;
  analyser.smoothingTimeConstant = 0.72;
  source.connect(analyser);

  const samples = new Uint8Array(analyser.fftSize);
  let frame = 0;
  let frameCount = 0;
  let stopped = false;
  const sample = () => {
    if (stopped) return;
    frameCount += 1;
    if (frameCount % 4 === 0) {
      analyser.getByteTimeDomainData(samples);
      let sumSquares = 0;
      for (const value of samples) {
        const centered = (value - 128) / 128;
        sumSquares += centered * centered;
      }
      onLevel(Math.min(1, Math.sqrt(sumSquares / samples.length) * 5));
    }
    frame = window.requestAnimationFrame(sample);
  };
  void context.resume();
  frame = window.requestAnimationFrame(sample);

  return () => {
    stopped = true;
    window.cancelAnimationFrame(frame);
    source.disconnect();
    analyser.disconnect();
    void context.close();
  };
}
