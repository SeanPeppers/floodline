// Convergence chart: real measured data from results.json (same numbers as
// the README's scaling table). Plain canvas 2D — no 3D geometry, no library.
// Exposes window.FloodlineChart.replay() so the "Simulate" button (main.js)
// can re-run the draw-in animation and keep the incident feed in step.
(function () {
  const canvas = document.getElementById("convergence-chart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Command-center severity palette: crimson = worst convergence (plain MC),
  // amber = best classical control (Sobol QMC), cyan = quantum (MLAE).
  const COLORS = {
    qae: "#00f5ff",
    mc: "#ff2a6d",
    qmc: "#ffb703",
    axis: "#94a3b8",
    grid: "rgba(148,163,184,0.15)",
  };

  let budgetsCache = null;
  let runToken = 0;

  fetch("assets/data/results.json")
    .then((r) => r.json())
    .then((data) => {
      budgetsCache = data.budgets;
      draw(budgetsCache);
    })
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
      qmc: budgets.map((b) => b.rmse_qmc),
    };
    const allVals = [...series.qae, ...series.mc, ...series.qmc];
    const xMin = Math.log10(Math.min(...queries)), xMax = Math.log10(Math.max(...queries));
    const yMin = Math.log10(Math.min(...allVals)), yMax = Math.log10(Math.max(...allVals));

    const X = (q) => pad.l + ((Math.log10(q) - xMin) / (xMax - xMin)) * plotW;
    const Y = (v) => pad.t + plotH - ((Math.log10(v) - yMin) / (yMax - yMin)) * plotH;

    function axesAndGrid() {
      ctx.strokeStyle = COLORS.grid;
      ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i++) {
        const y = pad.t + (plotH / 4) * i;
        ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(W - pad.r, y); ctx.stroke();
      }
      ctx.strokeStyle = COLORS.axis;
      ctx.beginPath(); ctx.moveTo(pad.l, pad.t); ctx.lineTo(pad.l, H - pad.b); ctx.lineTo(W - pad.r, H - pad.b); ctx.stroke();
      ctx.fillStyle = COLORS.axis;
      ctx.font = "13px 'JetBrains Mono', ui-monospace, monospace";
      ctx.fillText("queries (log scale) →", W / 2 - 70, H - 14);
      ctx.save();
      ctx.translate(18, H / 2 + 55);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText("RMSE vs true a (log scale)", 0, 0);
      ctx.restore();
    }

    function plotSeries(vals, color, frac) {
      const n = Math.max(1, Math.round(vals.length * frac));
      ctx.shadowColor = color;
      ctx.shadowBlur = 6;
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
      ctx.shadowBlur = 0;
    }

    function legend() {
      const items = [
        ["Plain Monte Carlo", COLORS.mc],
        ["Sobol QMC (classical, 2-D)", COLORS.qmc],
        ["Quantum MLAE", COLORS.qae],
      ];
      let lx = pad.l + 10, ly = pad.t + 14;
      ctx.font = "13px Inter, sans-serif";
      items.forEach(([label, color], i) => {
        const y = ly + i * 20;
        ctx.fillStyle = color;
        ctx.fillRect(lx, y - 8, 12, 12);
        ctx.fillStyle = "#f1f5f9";
        ctx.fillText(label, lx + 18, y + 2);
      });
    }

    function frame(f) {
      ctx.clearRect(0, 0, W, H);
      axesAndGrid();
      plotSeries(series.mc, COLORS.mc, f);
      plotSeries(series.qmc, COLORS.qmc, f);
      plotSeries(series.qae, COLORS.qae, f);
      legend();
    }

    if (reduceMotion) { frame(1); return; }

    const myToken = ++runToken;
    let frac = 0;
    function step() {
      if (myToken !== runToken) return; // a newer replay superseded this run
      frac += 0.02;
      frame(Math.min(frac, 1));
      if (frac < 1) requestAnimationFrame(step);
      else window.dispatchEvent(new CustomEvent("floodline:chart-done"));
    }
    requestAnimationFrame(step);
  }

  window.FloodlineChart = {
    replay() {
      if (budgetsCache) draw(budgetsCache);
    },
  };
})();
