// Convergence chart: real measured data from results.json (same numbers as
// the README's scaling table). Plain canvas 2D — no 3D geometry, no library.
(function () {
  const canvas = document.getElementById("convergence-chart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const COLORS = { qae: "#2dd4bf", mc: "#fbbf24", strat: "#5eb8ff", axis: "#a9bdcc", grid: "rgba(169,189,204,0.15)" };

  fetch("assets/data/results.json")
    .then((r) => r.json())
    .then((data) => draw(data.budgets))
    .catch(() => {
      ctx.fillStyle = COLORS.axis;
      ctx.font = "16px Inter, sans-serif";
      ctx.fillText("Convergence data unavailable offline.", 20, 40);
    });

  function draw(budgets) {
    const W = canvas.width, H = canvas.height;
    const pad = { l: 70, r: 30, t: 30, b: 50 };
    const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;

    const queries = budgets.map((b) => b.queries);
    const series = {
      qae: budgets.map((b) => b.rmse_qae),
      mc: budgets.map((b) => b.rmse_mc),
      strat: budgets.map((b) => b.rmse_strat),
    };
    const allVals = [...series.qae, ...series.mc, ...series.strat];
    const xMin = Math.log10(Math.min(...queries)), xMax = Math.log10(Math.max(...queries));
    const yMin = Math.log10(Math.min(...allVals)), yMax = Math.log10(Math.max(...allVals));

    const X = (q) => pad.l + ((Math.log10(q) - xMin) / (xMax - xMin)) * plotW;
    const Y = (v) => pad.t + plotH - ((Math.log10(v) - yMin) / (yMax - yMin)) * plotH;

    function drawStatic() {
      ctx.clearRect(0, 0, W, H);
      // grid
      ctx.strokeStyle = COLORS.grid;
      ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i++) {
        const y = pad.t + (plotH / 4) * i;
        ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(W - pad.r, y); ctx.stroke();
      }
      // axes
      ctx.strokeStyle = COLORS.axis;
      ctx.beginPath(); ctx.moveTo(pad.l, pad.t); ctx.lineTo(pad.l, H - pad.b); ctx.lineTo(W - pad.r, H - pad.b); ctx.stroke();
      ctx.fillStyle = COLORS.axis;
      ctx.font = "13px Inter, sans-serif";
      ctx.fillText("queries (log scale) →", W / 2 - 60, H - 14);
      ctx.save();
      ctx.translate(18, H / 2 + 50);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText("RMSE vs true a (log scale)", 0, 0);
      ctx.restore();

      plotSeries(series.mc, COLORS.mc, 1);
      plotSeries(series.strat, COLORS.strat, 1);
      plotSeries(series.qae, COLORS.qae, 1);
      legend();
    }

    function plotSeries(vals, color, frac) {
      const n = Math.max(1, Math.round(vals.length * frac));
      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const x = X(queries[i]), y = Y(vals[i]);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
      for (let i = 0; i < n; i++) {
        ctx.beginPath();
        ctx.arc(X(queries[i]), Y(vals[i]), 3.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    function legend() {
      const items = [["Plain Monte Carlo", COLORS.mc], ["Stratified sampling", COLORS.strat], ["Quantum MLAE", COLORS.qae]];
      let lx = pad.l + 10, ly = pad.t + 14;
      ctx.font = "13px Inter, sans-serif";
      items.forEach(([label, color], i) => {
        const y = ly + i * 20;
        ctx.fillStyle = color;
        ctx.fillRect(lx, y - 8, 12, 12);
        ctx.fillStyle = "#eef3f7";
        ctx.fillText(label, lx + 18, y + 2);
      });
    }

    if (reduceMotion) { drawStatic(); return; }

    // small animated draw-in, respects motion preference above
    let frac = 0;
    function step() {
      frac += 0.02;
      ctx.clearRect(0, 0, W, H);
      drawStaticFrame(Math.min(frac, 1));
      if (frac < 1) requestAnimationFrame(step);
    }
    function drawStaticFrame(f) {
      ctx.strokeStyle = COLORS.grid;
      ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i++) {
        const y = pad.t + (plotH / 4) * i;
        ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(W - pad.r, y); ctx.stroke();
      }
      ctx.strokeStyle = COLORS.axis;
      ctx.beginPath(); ctx.moveTo(pad.l, pad.t); ctx.lineTo(pad.l, H - pad.b); ctx.lineTo(W - pad.r, H - pad.b); ctx.stroke();
      ctx.fillStyle = COLORS.axis;
      ctx.font = "13px Inter, sans-serif";
      ctx.fillText("queries (log scale) →", W / 2 - 60, H - 14);
      plotSeries(series.mc, COLORS.mc, f);
      plotSeries(series.strat, COLORS.strat, f);
      plotSeries(series.qae, COLORS.qae, f);
      legend();
    }
    requestAnimationFrame(step);
  }
})();
