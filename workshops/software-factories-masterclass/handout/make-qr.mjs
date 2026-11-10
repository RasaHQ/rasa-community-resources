// Writes qr.svg for the Codespaces launch link. Run with the QR encoder that ships with npm:
//   QR_VENDOR=/opt/homebrew/lib/node_modules/npm/node_modules/qrcode-terminal/vendor/QRCode node handout/make-qr.mjs
import { createRequire } from 'node:module';
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const QRCode = require(process.env.QR_VENDOR);
const level = require(process.env.QR_VENDOR + '/QRErrorCorrectLevel');
const url = 'https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/travel-factory/devcontainer.json';
let qr;
for (let type = 4; type <= 40; type++) {
  try { qr = new QRCode(type, level.M); qr.addData(url); qr.make(); break; } catch (e) { qr = null; }
}
if (!qr) throw new Error('link does not fit');
const n = qr.getModuleCount(), border = 4;
let path = '';
for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) path += `M${c + border} ${r + border}h1v1h-1z`;
const size = n + border * 2;
writeFileSync(fileURLToPath(new URL('./qr.svg', import.meta.url)),
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" shape-rendering="crispEdges"><rect width="${size}" height="${size}" fill="#fff"/><path d="${path}" fill="#000"/></svg>\n`);
console.log('modules', n, 'version', qr.typeNumber);
