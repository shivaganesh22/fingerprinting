// Tracker script performing canvas and audio fingerprinting
(function() {
  const canvas = document.createElement('canvas');
  canvas.width = 150;
  canvas.height = 30;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#ff00aa';
  ctx.fillRect(0, 0, 100, 20);
  ctx.fillStyle = '#00bbcc';
  ctx.font = '14px sans-serif';
  ctx.fillText('TrackingID:998877', 10, 15);
  const fp = canvas.toDataURL();
  window.__tracker_fp = fp;
  console.log("3rd party tracker executed canvas fingerprinting");
})();
