import React from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  Clock,
  Download,
  RefreshCw,
  ShieldCheck,
  Smartphone,
  TrendingDown,
  TrendingUp,
  Users,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  fetchProductAnalyticsDashboard,
  type AuthSession,
  type ProductAnalyticsDashboard,
  type ProductFeatureUsage,
} from "../../../services/api";

const DEVICE_COLORS: Record<string, string> = {
  Android: "#0F766E",
  iOS: "#2563EB",
  Web: "#C8A84B",
  USSD: "#7C3AED",
};

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return minutes > 0 ? `${minutes}m ${remaining}s` : `${remaining}s`;
}

function metricTone(value: number, inverse = false): string {
  const good = inverse ? value < 35 : value >= 50;
  return good ? "text-emerald-600" : "text-amber-600";
}

function KpiCard({ label, value, hint, icon: Icon, tone }: { label: string; value: string; hint: string; icon: React.ElementType; tone?: string }) {
  return (
    <div className="bg-card border border-border rounded-lg p-4 min-w-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className={`mt-2 text-2xl font-bold font-['JetBrains_Mono',_monospace] ${tone ?? "text-foreground"}`}>{value}</p>
        </div>
        <div className="w-9 h-9 rounded-lg bg-secondary flex items-center justify-center flex-shrink-0">
          <Icon size={17} className="text-primary" />
        </div>
      </div>
      <p className="text-xs text-muted-foreground mt-3 leading-relaxed">{hint}</p>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="bg-card border border-border rounded-lg p-8 text-center">
      <div className="mx-auto w-12 h-12 rounded-full bg-secondary flex items-center justify-center">
        <Activity size={20} className="text-muted-foreground" />
      </div>
      <p className="mt-3 text-sm font-semibold text-foreground">No analytics data loaded</p>
      <p className="mt-1 text-xs text-muted-foreground">Track product events or refresh after the backend starts.</p>
    </div>
  );
}

function FeatureRow({ feature }: { feature: ProductFeatureUsage }) {
  return (
    <tr className="border-b border-border last:border-0">
      <td className="px-4 py-3">
        <div>
          <p className="text-sm font-medium text-foreground">{feature.label}</p>
          <p className="text-xs text-muted-foreground">{feature.feature}</p>
        </div>
      </td>
      <td className="px-4 py-3 text-sm text-foreground font-['JetBrains_Mono',_monospace]">{feature.usageCount.toLocaleString()}</td>
      <td className="px-4 py-3 text-sm text-foreground font-['JetBrains_Mono',_monospace]">{feature.uniqueUsers.toLocaleString()}</td>
      <td className="px-4 py-3 text-sm text-foreground">{feature.adoptionRate}%</td>
      <td className="px-4 py-3 text-sm text-foreground">{formatDuration(feature.avgDurationSeconds)}</td>
      <td className="px-4 py-3">
        <span className={`inline-flex items-center gap-1 text-xs font-semibold ${feature.trend === "up" ? "text-emerald-600" : "text-amber-600"}`}>
          {feature.trend === "up" ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
          {feature.trend}
        </span>
      </td>
    </tr>
  );
}

export function ProductUsageAnalyticsDashboard({ session }: { session: AuthSession }) {
  const [days, setDays] = React.useState(30);
  const [dashboard, setDashboard] = React.useState<ProductAnalyticsDashboard | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");

  const loadDashboard = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setDashboard(await fetchProductAnalyticsDashboard(session.token, days));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load product analytics");
    } finally {
      setLoading(false);
    }
  }, [days, session.token]);

  React.useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  if (session.user.role !== "admin") {
    return (
      <div className="bg-card border border-border rounded-lg p-6 flex items-start gap-3">
        <ShieldCheck size={18} className="text-primary flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-foreground">Admin access required</p>
          <p className="text-xs text-muted-foreground mt-1">Product usage analytics include sensitive member behavior and are restricted to admins.</p>
        </div>
      </div>
    );
  }

  if (loading && !dashboard) {
    return (
      <div className="bg-card border border-border rounded-lg p-6 flex items-center gap-3">
        <RefreshCw size={16} className="text-primary animate-spin" />
        <p className="text-sm text-muted-foreground">Loading product usage analytics...</p>
      </div>
    );
  }

  if (!dashboard) return <EmptyState />;

  const kpis = dashboard.kpis;
  const worstDropOff = dashboard.funnel.reduce((max, step) => step.dropOffFromPrevious > max.dropOffFromPrevious ? step : max, dashboard.funnel[0]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-foreground font-['Plus_Jakarta_Sans']">Usage Analytics</h2>
          <p className="text-xs text-muted-foreground mt-1">Generated {new Date(dashboard.generatedAt).toLocaleString()} from product events and loan workflow signals.</p>
        </div>
        <div className="flex items-center gap-2 overflow-x-auto">
          <div className="flex gap-1 p-1 bg-secondary rounded-lg">
            {[7, 30, 90].map((option) => (
              <button
                key={option}
                onClick={() => setDays(option)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-md whitespace-nowrap ${days === option ? "bg-card text-foreground shadow-sm" : "text-muted-foreground"}`}
              >
                {option}d
              </button>
            ))}
          </div>
          <button onClick={loadDashboard} className="h-8 w-8 rounded-lg border border-border bg-card flex items-center justify-center hover:bg-secondary transition-colors" title="Refresh analytics">
            <RefreshCw size={14} className={loading ? "animate-spin text-primary" : "text-muted-foreground"} />
          </button>
          <button className="h-8 w-8 rounded-lg border border-border bg-card flex items-center justify-center hover:bg-secondary transition-colors" title="Export report">
            <Download size={14} className="text-muted-foreground" />
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-2">
          <AlertTriangle size={15} className="text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-red-700">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-6 gap-4">
        <KpiCard label="DAU" value={kpis.dau.toLocaleString()} hint="Unique users active today" icon={Users} />
        <KpiCard label="MAU" value={kpis.mau.toLocaleString()} hint="Unique users in the last 30 days" icon={Activity} />
        <KpiCard label="Session Duration" value={formatDuration(kpis.avgSessionDurationSeconds)} hint="Average tracked session time" icon={Clock} />
        <KpiCard label="Bounce Rate" value={`${kpis.bounceRate}%`} hint="Single-action sessions" icon={TrendingDown} tone={metricTone(kpis.bounceRate, true)} />
        <KpiCard label="Retention" value={`${kpis.retentionRate}%`} hint="Returning users across weeks" icon={TrendingUp} tone={metricTone(kpis.retentionRate)} />
        <KpiCard label="Loan Conversion" value={`${kpis.conversionRate}%`} hint="Started to submitted" icon={ShieldCheck} tone={metricTone(kpis.conversionRate)} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2 bg-card border border-border rounded-lg p-5 min-w-0">
          <div className="flex items-center justify-between mb-4 gap-3">
            <div>
              <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Active Users and Conversion Trends</h3>
              <p className="text-xs text-muted-foreground mt-0.5">Daily usage alongside loan conversion rate</p>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={dashboard.timeSeries} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,76,53,0.08)" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#5A6B60" }} axisLine={false} tickLine={false} tickFormatter={(value) => value.slice(5)} />
              <YAxis yAxisId="left" tick={{ fontSize: 11, fill: "#5A6B60" }} axisLine={false} tickLine={false} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: "#5A6B60" }} axisLine={false} tickLine={false} tickFormatter={(value) => `${value}%`} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--border)" }} />
              <Area yAxisId="left" type="monotone" dataKey="activeUsers" name="Active users" stroke="#0F766E" fill="#0F766E" fillOpacity={0.14} strokeWidth={2.5} />
              <Line yAxisId="right" type="monotone" dataKey="conversionRate" name="Conversion rate" stroke="#C8A84B" strokeWidth={2.5} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-card border border-border rounded-lg p-5 min-w-0">
          <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Device Breakdown</h3>
          <p className="text-xs text-muted-foreground mt-0.5 mb-4">Android, iOS, Web, and USSD sessions</p>
          <ResponsiveContainer width="100%" height={205}>
            <PieChart>
              <Pie data={dashboard.deviceBreakdown} dataKey="sessions" nameKey="device" innerRadius={52} outerRadius={82} paddingAngle={3}>
                {dashboard.deviceBreakdown.map((row) => <Cell key={row.device} fill={DEVICE_COLORS[row.device] ?? "#64748B"} />)}
              </Pie>
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--border)" }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 gap-2 mt-2">
            {dashboard.deviceBreakdown.map((row) => (
              <div key={row.device} className="flex items-center gap-2 text-xs">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: DEVICE_COLORS[row.device] ?? "#64748B" }} />
                <span className="text-muted-foreground">{row.device}</span>
                <span className="ml-auto font-semibold text-foreground">{row.share}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        <div className="xl:col-span-3 bg-card border border-border rounded-lg p-5 min-w-0">
          <div className="flex items-center justify-between gap-3 mb-4">
            <div>
              <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Loan Application Funnel</h3>
              <p className="text-xs text-muted-foreground mt-0.5">Step conversion with drop-off percentage</p>
            </div>
            <span className="text-xs px-2 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
              Worst: {worstDropOff?.label}
            </span>
          </div>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={dashboard.funnel} layout="vertical" margin={{ top: 0, right: 20, left: 24, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,76,53,0.08)" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: "#5A6B60" }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="label" width={118} tick={{ fontSize: 11, fill: "#32453A" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--border)" }} />
              <Bar dataKey="users" name="Users" fill="#0F766E" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-2 mt-4">
            {dashboard.funnel.map((step) => (
              <div key={step.step} className="p-3 rounded-lg border border-border bg-secondary/20">
                <p className="text-xs font-semibold text-foreground truncate">{step.label}</p>
                <p className="text-lg font-bold text-foreground font-['JetBrains_Mono',_monospace]">{step.conversionFromStart}%</p>
                <p className="text-xs text-muted-foreground">Drop-off {step.dropOffFromPrevious}%</p>
              </div>
            ))}
          </div>
        </div>

        <div className="xl:col-span-2 bg-card border border-border rounded-lg p-5 min-w-0">
          <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Real-Time Alerts</h3>
          <p className="text-xs text-muted-foreground mt-0.5 mb-4">Anomalies for error spikes, active-user dips, and funnel drop-offs</p>
          <div className="space-y-3">
            {dashboard.alerts.length === 0 && <p className="text-sm text-muted-foreground">No open product analytics alerts.</p>}
            {dashboard.alerts.map((alert, index) => (
              <div key={`${alert.id}-${index}`} className="p-3 rounded-lg border border-border bg-secondary/20 flex gap-3">
                <AlertTriangle size={15} className={alert.severity === "high" ? "text-red-600" : "text-amber-600"} />
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-foreground">{alert.title}</p>
                  <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{alert.description}</p>
                  <p className="text-xs font-['JetBrains_Mono',_monospace] text-muted-foreground mt-2">{alert.metric}: {alert.currentValue} / {alert.thresholdValue}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="bg-card border border-border rounded-lg overflow-hidden min-w-0">
          <div className="p-5 border-b border-border">
            <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Feature Usage</h3>
            <p className="text-xs text-muted-foreground mt-0.5">Balance checks, loans, chatbot, and statements</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px]">
              <thead className="bg-secondary/50">
                <tr>
                  {["Feature", "Uses", "Users", "Adoption", "Avg Time", "Trend"].map((head) => (
                    <th key={head} className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">{head}</th>
                  ))}
                </tr>
              </thead>
              <tbody>{dashboard.featureUsage.map((feature) => <FeatureRow key={feature.feature} feature={feature} />)}</tbody>
            </table>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-5 min-w-0">
          <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Friction Points and AI Fixes</h3>
          <p className="text-xs text-muted-foreground mt-0.5 mb-4">Recommendations generated from usage patterns</p>
          <div className="space-y-3">
            {dashboard.frictionPoints.map((point) => (
              <div key={point.area} className="p-4 rounded-lg border border-border bg-secondary/20">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${point.severity === "high" ? "bg-red-50 text-red-700 border border-red-200" : "bg-amber-50 text-amber-700 border border-amber-200"}`}>
                    {point.severity}
                  </span>
                  <p className="text-sm font-semibold text-foreground">{point.area}</p>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">{point.signal}</p>
                <p className="text-xs text-foreground leading-relaxed mt-2">
                  <Bot size={12} className="inline mr-1 text-primary" />
                  {point.aiRecommendation}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-card border border-border rounded-lg p-5">
        <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">AI Insights</h3>
        <p className="text-xs text-muted-foreground mt-0.5 mb-4">Generated from active-user, conversion, channel, and feature patterns</p>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {dashboard.insights.map((insight, index) => (
            <div key={`${insight.title}-${index}`} className="p-4 rounded-lg border border-border bg-secondary/20">
              <div className="flex items-center gap-2 mb-3">
                <Smartphone size={15} className="text-primary" />
                <span className="text-xs font-semibold text-primary">{insight.category}</span>
                <span className="ml-auto text-xs font-['JetBrains_Mono',_monospace] text-muted-foreground">{insight.confidence}%</span>
              </div>
              <p className="text-sm font-semibold text-foreground">{insight.title}</p>
              <p className="text-xs text-muted-foreground leading-relaxed mt-2">{insight.narrative}</p>
              <p className="text-xs text-foreground leading-relaxed mt-3">{insight.recommendation}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
