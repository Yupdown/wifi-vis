declare module 'utif' {
  interface Directory { width: number; height: number; }
  const UTIF: {
    decode(buffer: ArrayBuffer): Directory[];
    decodeImage(buffer: ArrayBuffer, directory: Directory): void;
    toRGBA8(directory: Directory): Uint8Array;
  };
  export default UTIF;
}
