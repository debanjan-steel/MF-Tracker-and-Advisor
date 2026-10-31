/**
 * generate-icons.mjs — Run once with: node generate-icons.mjs
 * Creates SVG-based PNG icons for the PWA manifest.
 * No external dependencies needed beyond Node.js built-ins.
 */
import { writeFileSync, mkdirSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

const SVG = (size) => `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <rect width="${size}" height="${size}" rx="${size * 0.2}" fill="#4f46e5"/>
  <polyline
    points="${size*0.25} ${size*0.7} ${size*0.44} ${size*0.32} ${size*0.625} ${size*0.57} ${size*0.75} ${size*0.45}"
    fill="none" stroke="white" stroke-width="${size*0.075}" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="${size*0.75}" cy="${size*0.45}" r="${size*0.075}" fill="#22c55e"/>
</svg>`

const outDir = join(__dirname, 'public', 'icons')
mkdirSync(outDir, { recursive: true })

for (const size of [192, 512]) {
  writeFileSync(join(outDir, `icon-${size}.svg`), SVG(size))
  console.log(`✓ icon-${size}.svg written`)
}

console.log(`
NOTE: For production PNG icons (required by Android PWA install),
convert the SVGs using:
  npx sharp-cli -i public/icons/icon-192.svg -o public/icons/icon-192.png resize 192 192
  npx sharp-cli -i public/icons/icon-512.svg -o public/icons/icon-512.png resize 512 512

Or use any online SVG→PNG converter and save as icon-192.png / icon-512.png in public/icons/
`)

