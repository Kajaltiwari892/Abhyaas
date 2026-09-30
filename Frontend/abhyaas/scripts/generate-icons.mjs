// Rasterize the code-native SVG for legacy browsers and Apple home screens.
// No fonts, remote resources, or image-generation service are needed at runtime.
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const app = new URL("../app/", import.meta.url);
const source = await readFile(new URL("icon.svg", app));
const sizes = [16, 32, 48, 64];
const images = await Promise.all(sizes.map((size) => sharp(source).resize(size, size).png().toBuffer()));
const header = Buffer.alloc(6 + sizes.length * 16);
header.writeUInt16LE(1, 2);
header.writeUInt16LE(sizes.length, 4);
let offset = header.length;
for (let i = 0; i < sizes.length; i++) {
  const entry = 6 + i * 16;
  header[entry] = sizes[i];
  header[entry + 1] = sizes[i];
  header.writeUInt16LE(1, entry + 4);
  header.writeUInt16LE(32, entry + 6);
  header.writeUInt32LE(images[i].length, entry + 8);
  header.writeUInt32LE(offset, entry + 12);
  offset += images[i].length;
}
await writeFile(new URL("favicon.ico", app), Buffer.concat([header, ...images]));
await sharp(source).resize(180, 180).png().toFile(fileURLToPath(new URL("apple-icon.png", app)));
console.log("Generated 16/32/48/64px favicon and 180px Apple icon from icon.svg");
