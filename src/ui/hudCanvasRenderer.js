import {
  STAGES,
  getPhysicalTime,
  getTemperature,
  getActiveStage,
  smoothstep
} from '../timeline.js';

function drawRoundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function drawSciNotation(ctx, text, x, y, fontSize) {
  // Renders strings like "1.4 x 10^-43 s" or "~3.0 s" cleanly with superscripts
  const match = text.match(/^(.*?)10\^(-?\d+)(.*)$/);
  if (!match) {
    ctx.font = `500 ${fontSize}px "JetBrains Mono", monospace`;
    ctx.fillText(text.replace('x', '×'), x, y);
    return;
  }

  const prefix = match[1].replace('x', '×');
  const exp = match[2].replace('-', '−');
  const suffix = match[3];

  ctx.font = `500 ${fontSize}px "JetBrains Mono", monospace`;
  let cursor = x;
  if (prefix) {
    ctx.fillText(prefix, cursor, y);
    cursor += ctx.measureText(prefix).width;
  }
  ctx.fillText('10', cursor, y);
  cursor += ctx.measureText('10').width;

  const supSize = Math.round(fontSize * 0.68);
  ctx.font = `500 ${supSize}px "JetBrains Mono", monospace`;
  ctx.fillText(exp, cursor + 1, y - fontSize * 0.36);
  cursor += ctx.measureText(exp).width + 2;

  ctx.font = `500 ${fontSize}px "JetBrains Mono", monospace`;
  if (suffix) {
    ctx.fillText(suffix, cursor, y);
  }
}

export function drawHudOnCanvas(ctx, width, height, u, labelsVisible) {
  const physTime = getPhysicalTime(u);
  const temp = getTemperature(u);
  const active = getActiveStage(u);

  ctx.save();
  ctx.textBaseline = 'alphabetic';

  // 1. Top-left persistent telemetry card
  const boxX = 40;
  const boxY = 36;
  const boxW = 540;
  const boxH = 92;

  drawRoundRect(ctx, boxX, boxY, boxW, boxH, 16);
  ctx.fillStyle = 'rgba(10, 12, 20, 0.56)';
  ctx.fill();
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.18)';
  ctx.stroke();

  ctx.fillStyle = 'rgba(226, 236, 255, 0.72)';
  ctx.font = '600 14px "Inter", sans-serif';
  ctx.fillText('TIME AFTER BIG BANG', boxX + 24, boxY + 32);
  ctx.fillText('TEMPERATURE', boxX + 296, boxY + 32);

  ctx.fillStyle = '#ffffff';
  drawSciNotation(ctx, physTime.formattedPlain, boxX + 24, boxY + 68, 25);
  drawSciNotation(ctx, temp.formattedPlain, boxX + 296, boxY + 68, 25);

  ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
  ctx.beginPath();
  ctx.moveTo(boxX + 272, boxY + 20);
  ctx.lineTo(boxX + 272, boxY + 72);
  ctx.stroke();

  // 2. Top-right core concept caption (u = 0..4.5s)
  if (labelsVisible) {
    const capOpacity = 1.0 - smoothstep(3.8, 4.6, u);
    if (capOpacity > 0.01) {
      ctx.save();
      ctx.globalAlpha = capOpacity;
      const cw = 620;
      const ch = 84;
      const cx = width - cw - 40;
      const cy = 36;

      drawRoundRect(ctx, cx, cy, cw, ch, 16);
      ctx.fillStyle = 'rgba(10, 12, 20, 0.56)';
      ctx.fill();
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.18)';
      ctx.stroke();

      ctx.fillStyle = 'rgba(255, 255, 255, 0.94)';
      ctx.font = '400 18px "Inter", sans-serif';
      ctx.fillText('The Big Bang happened everywhere at once — not an explosion from', cx + 22, cy + 36);
      ctx.fillText('a point. Moving outward from the center represents time, not space.', cx + 22, cy + 62);
      ctx.restore();
    }
  }

  // 3. Lower-third documentary stage label
  if (labelsVisible && active.opacity > 0.01) {
    ctx.save();
    ctx.globalAlpha = active.opacity;
    ctx.textAlign = 'center';

    const centerX = width * 0.5;
    const baseY = height - 86;

    const grad = ctx.createRadialGradient(centerX, baseY - 38, 40, centerX, baseY - 38, 460);
    grad.addColorStop(0, 'rgba(8, 10, 18, 0.62)');
    grad.addColorStop(0.7, 'rgba(8, 10, 18, 0.34)');
    grad.addColorStop(1, 'rgba(8, 10, 18, 0.0)');
    ctx.fillStyle = grad;
    ctx.fillRect(centerX - 500, baseY - 120, 1000, 150);

    ctx.shadowColor = 'rgba(0, 0, 0, 0.85)';
    ctx.shadowBlur = 16;

    ctx.fillStyle = 'rgba(226, 240, 255, 0.92)';
    ctx.font = '500 17px "JetBrains Mono", monospace';
    ctx.fillText(`STAGE ${active.stageIndex + 1} / ${STAGES.length}   •   ${active.stage.epoch}`, centerX, baseY - 72);

    ctx.fillStyle = '#ffffff';
    ctx.font = '600 42px "Inter", sans-serif';
    ctx.fillText(active.stage.title, centerX, baseY - 26);

    ctx.fillStyle = 'rgba(246, 249, 255, 0.94)';
    ctx.font = '400 22px "Inter", sans-serif';
    ctx.fillText(active.subtitle, centerX, baseY + 14);
    ctx.restore();
  }

  ctx.restore();
}
