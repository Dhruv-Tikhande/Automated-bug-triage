import { useMemo, useState } from "react";
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  Clock3,
  Loader2,
  ShieldAlert,
  Sparkles,
  TriangleAlert,
  Terminal,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// 1. UPDATED: These are the actual modules your AI learned from the Netbeans Dataset
const moduleOptions = [
  "java",
  "utilities",
  "platform",
  "apisupport",
  "cnd",
  "php",
  "web",
  "ide",
  "xml",
  "mobility"
];

const chartData = [
  { team: "Editor", bugs: 319, color: "#22D3EE" },
  { team: "Code", bugs: 294, color: "#0EA5E9" },
  { team: "Source", bugs: 269, color: "#10B981" },
  { team: "Code Model", bugs: 218, color: "#F59E0B" },
];

const recentTriages = [
  {
    id: "BUG-2311",
    title: "NullPointerException at DiffSplitPaneDivider",
    severity: "Critical",
    status: "Assigned",
    team: "Diff",
  },
  {
    id: "BUG-2310",
    title: "Wrong autocompletion with casts",
    severity: "High",
    status: "Assigned",
    team: "Editor",
  },
  {
    id: "BUG-2309",
    title: "java.util.MissingResourceException in autoupdate",
    severity: "Critical",
    status: "In Review",
    team: "Autoupdate",
  },
];

function statusClass(severity) {
  if (severity === "Critical") {
    return "bg-red-500/20 text-red-400 border-red-500/30";
  }
  if (severity === "High") {
    return "bg-orange-500/20 text-orange-400 border-orange-500/30";
  }
  return "bg-blue-500/20 text-blue-400 border-blue-500/30";
}

function App() {
  const [description, setDescription] = useState("");
  // Default to 'java' since it's the most common
  const [failingModule, setFailingModule] = useState("java");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const flakinessColor = useMemo(() => {
    if (!result) return "text-slate-400";
    const val = parseFloat(result.flakiness_probability);
    if (val > 50) return "text-red-400";
    if (val > 20) return "text-orange-400";
    return "text-green-400";
  }, [result]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!description.trim()) {
      setError("Please provide a bug description.");
      return;
    }
    
    setLoading(true);
    setError("");
    setResult(null); // Clear previous result for the animation

    const payload = {
      description: description.trim(),
      module: failingModule, // Changed to match FastAPI expected payload
    };

    try {
      const response = await fetch(`${API_BASE_URL}/api/predict_bug`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error("Prediction endpoint returned a non-success response.");
      }

      const data = await response.json();
      setResult(data);
    } catch (fetchError) {
      setError("Backend unavailable. Make sure your Python server is running.");
      console.error(fetchError);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-10">
        <header className="mb-8 rounded-2xl border border-slate-800 bg-slate-900/50 p-5 shadow-lg backdrop-blur-md">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="mb-1 flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-slate-400">
                <Sparkles className="h-4 w-4 text-cyan-400" />
                Automated QA Intelligence
              </p>
              <h1 className="text-2xl font-bold tracking-tight text-white md:text-3xl">
                Bug Triage & Routing
              </h1>
            </div>
            <div className="flex items-center gap-2 rounded-full border border-cyan-500/40 bg-cyan-500/10 px-4 py-1.5 text-sm font-medium text-cyan-400">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-75"></span>
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-cyan-500"></span>
              </span>
              Neural Network Active
            </div>
          </div>
        </header>

        <section className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
          <div className="space-y-6">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
              <div className="mb-5 flex items-center gap-3">
                <Bot className="h-5 w-5 text-cyan-400" />
                <h2 className="text-xl font-semibold text-white">Analyze Issue</h2>
              </div>

              <form className="space-y-5" onSubmit={handleSubmit}>
                <div>
                  <label htmlFor="description" className="mb-2 block text-sm font-medium text-slate-400">
                    Bug Description
                  </label>
                  <textarea
                    id="description"
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    placeholder="E.g., The application crashes with a NullPointerException when trying to save the java file..."
                    className="h-36 w-full resize-none rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-200 outline-none transition focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
                  />
                </div>

                <div>
                  <label htmlFor="module" className="mb-2 block text-sm font-medium text-slate-400">
                    Suspected Module
                  </label>
                  <select
                    id="module"
                    value={failingModule}
                    onChange={(event) => setFailingModule(event.target.value)}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-200 outline-none transition focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
                  >
                    {moduleOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Running Neural Fusion...
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" />
                      Run AI Triage
                    </>
                  )}
                </button>
              </form>
            </div>

            {/* RESULTS SECTION */}
            <div className={`rounded-2xl border border-slate-800 p-6 shadow-xl transition-all duration-500 ${result ? 'bg-slate-800/50' : 'bg-slate-900'}`}>
              <h3 className="mb-4 text-lg font-semibold text-white">Triage Results</h3>
              
              {error && (
                <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-400">
                  <AlertCircle className="h-4 w-4" />
                  {error}
                </div>
              )}

              {!result && !loading && !error && (
                <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-700 bg-slate-950/50 py-10 text-center text-sm text-slate-500">
                  <Terminal className="mb-2 h-8 w-8 opacity-50" />
                  Awaiting input data.
                </div>
              )}

              {loading && (
                <div className="flex animate-pulse flex-col gap-3">
                  <div className="h-16 w-full rounded-xl bg-slate-800"></div>
                  <div className="h-12 w-full rounded-xl bg-slate-800"></div>
                  <div className="h-12 w-full rounded-xl bg-slate-800"></div>
                </div>
              )}

              {result && !loading && (
                <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                  {/* Highlighted Top Result */}
                  <div className="flex items-center justify-between rounded-xl border border-cyan-500/30 bg-gradient-to-r from-cyan-500/10 to-transparent px-5 py-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-cyan-500/20">
                        <CheckCircle2 className="h-5 w-5 text-cyan-400" />
                      </div>
                      <div>
                        <span className="block text-xs font-medium uppercase tracking-wider text-slate-400">Routed To Team</span>
                        <span className="block text-lg font-bold text-white">{result.assigned_team}</span>
                      </div>
                    </div>
                  </div>

                  <MetricRow
                    label="AI Confidence Score"
                    value={result.confidence}
                    icon={<Clock3 className="h-4 w-4 text-blue-400" />}
                  />
                  <MetricRow
                    label="Flakiness Probability"
                    value={result.flakiness_probability}
                    valueColor={flakinessColor}
                    icon={<TriangleAlert className="h-4 w-4 text-orange-400" />}
                    tooltip="Estimated chance this failure is non-deterministic, generated via Bayesian Network."
                  />
                </div>
              )}
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
              <h3 className="mb-4 text-lg font-semibold text-white">
                Historical Distribution (Netbeans Data)
              </h3>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="team" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                    <YAxis stroke="#94a3b8" allowDecimals={false} />
                    <Tooltip
                      cursor={{ fill: "rgba(51, 65, 85, 0.4)" }}
                      contentStyle={{
                        background: "#0f172a",
                        border: "1px solid #1e293b",
                        borderRadius: "12px",
                        color: "#f1f5f9",
                      }}
                    />
                    <Legend />
                    <Bar name="Bugs Handled" dataKey="bugs" radius={[6, 6, 0, 0]}>
                      {chartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
              <div className="mb-4 flex items-center gap-2">
                <ShieldAlert className="h-5 w-5 text-cyan-400" />
                <h3 className="text-lg font-semibold text-white">Recent Triage History</h3>
              </div>

              <div className="space-y-3">
                {recentTriages.map((bug) => (
                  <article
                    key={bug.id}
                    className="rounded-xl border border-slate-800 bg-slate-950/50 px-4 py-3 transition hover:border-slate-700"
                  >
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
                        {bug.id}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${statusClass(bug.severity)}`}>
                          {bug.severity}
                        </span>
                      </div>
                    </div>
                    <p className="mb-1 text-sm font-medium text-slate-200">{bug.title}</p>
                    <p className="text-xs text-slate-400">Routed to: <span className="font-medium text-cyan-400">{bug.team}</span></p>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

function MetricRow({ label, value, icon, tooltip, valueColor = "text-white" }) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950 px-5 py-4 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900">
          {icon}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-medium text-slate-300">{label}</span>
          {tooltip && (
            <span
              className="mt-0.5 inline-flex h-3.5 w-3.5 cursor-help items-center justify-center rounded-full border border-slate-600 text-[9px] text-slate-400 hover:border-slate-400 hover:text-slate-300 transition-colors"
              title={tooltip}
            >
              ?
            </span>
          )}
        </div>
      </div>
      <span className={`text-lg font-bold ${valueColor}`}>{value}</span>
    </div>
  );
}

export default App;