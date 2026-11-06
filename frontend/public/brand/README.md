# HealthWise AI brand files

The mark is a geometric **heart with a pulse line cut out of it** (a node at each end of the line): care, and a reading of the heartbeat. The pulse and nodes are
real holes, so the mark works on any background. It is drawn by hand as vector paths; there are no raster images and no generated imagery inside any SVG.

Everything the app and the stores need is in this folder. The app draws the logo from `src/components/brandPaths.js` (the same paths, generated from these files),
so change the logo here first and regenerate; do not edit that file by hand.

## Files

| File | Use |
|---|---|
| `logo-horizontal.svg`, `-dark`, `-white` | mark and name side by side: full colour (on white), one colour dark (print), one colour white (on dark or coloured surfaces) |
| `logo-stacked.svg`, `-dark`, `-white` | mark above the name (square-ish spaces, covers, sign-in cards) |
| `logo-mark.svg`, `-dark`, `-white` | the heart alone (small spaces, avatars) |
| `logo-wordmark.svg`, `-dark`, `-white` | the name alone |
| `favicon.svg` | browser tab; follows the light and dark mode of the browser |
| `favicon.ico` (16, 32, 48), `favicon-32.png` | older browsers |
| `icons/icon.svg`, `icons/icon-{1024,512,192,180,167,152,120,96,72,48}.png` | app icon (rounded tile); 1024 is for the store listing, 180 is the Apple touch icon |
| `icons/icon-maskable.svg`, `icons/icon-maskable-{192,512}.png` | PWA maskable icon (full bleed, the mark inside the safe circle) |
| `icons/android-adaptive-foreground.svg` / `-432.png`, `icons/android-adaptive-background.svg` / `-432.png` | Android adaptive icon layers (mark inside the 66% safe zone) |
| `icons/android-monochrome.svg` / `-432.png`, `icons/notification-96.png` | Android themed icon and notification icon (white on transparent) |
| `splash-light.png/.svg`, `splash-dark.png/.svg` | native splash (1080 x 1920): the mark centred on the brand colour, the same first frame as the web launch screen. The app uses the brand-colour one in both light and dark mode. |
| `og-image.png/.svg` | share image, 1200 x 630 |

Android launcher icons and splash images in `android/app/src/main/res` are generated from the same drawing.

## Palette

| Role | Hex | Contrast |
|---|---|---|
| Primary | `#0A7C99` | 4.8 : 1 with white text, 4.6 : 1 on the light tint |
| Deep | `#164E63` | 9.1 : 1 with white; the theme colour and launch colour |
| Bright accent | `#22D3EE` | 5.0 : 1 on deep, 9.9 : 1 on dark; not for text on white (1.8 : 1) |
| Neutral dark | `#0F172A` | 17.9 : 1 on white |
| Light tint | `#ECFEFF` | page tints; deep text on it is 8.8 : 1 |

The full-colour mark is a gradient from deep to primary to bright. Use it on white or the light tint. On the brand teal or on dark use the **white** version
(white on deep is 9.1 : 1, on dark 17.9 : 1). The pale cyan tip of the gradient is below 3 : 1 on white, so for strict contrast (stamps, forms, black-and-white print) use the one-colour dark version.

## Wordmark font

**Manrope** (SIL Open Font License 1.1, free for commercial use, Google Fonts): "HealthWise" in weight 800, "AI" in weight 500 in the accent colour. In every logo
file the text is converted to outlines, so no font is loaded and nothing depends on a font being installed. The app interface keeps the system font.

## Clear space and minimum size

- Clear space on every side: the height of the heart's lobes (one quarter of the mark's height). Nothing else sits inside it.
- Minimum size: the mark 16 px (digital) or 5 mm (print); the horizontal logo 96 px wide, the stacked logo 64 px wide. Below that use the mark alone.

## Do

- Use the files as they are, on white, the light tint, the brand teal or dark.
- Use the white version on dark or coloured surfaces and the one-colour dark version for black-and-white print and stamps.

## Don't

- Don't stretch, rotate, outline, add shadows or effects, or change the proportions of the mark and name.
- Don't recolour outside the palette, and don't put the full-colour gradient on a busy photo or a mid-teal background (use the white version).
- Don't redraw the heart or the pulse, and don't separate the "AI" from the name in the wordmark.
- Don't use the logo of another organisation next to it at a larger size than this one.
