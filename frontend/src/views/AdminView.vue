<template>
  <div class="page-shell admin-console">
    <div class="page-hero admin-hero">
      <div>
        <p class="page-eyebrow">Admin Console</p>
        <h2 class="page-title">企业管理台</h2>
        <p class="page-desc">服务健康、租户用量、安全策略与审计轨迹的统一观测入口。</p>
      </div>
      <div class="admin-hero__actions">
        <div class="admin-live" :class="{ 'is-loading': adminLoading }">
          <span class="admin-live__dot" />
          <span>{{ adminLoading ? '同步中' : '已同步' }}</span>
          <span v-if="lastSyncedAt" class="admin-live__time">{{ lastSyncedAt }}</span>
        </div>
        <button
          type="button"
          class="admin-refresh"
          :disabled="adminLoading"
          @click="loadAdminConsole"
        >
          <span class="admin-refresh__icon" :class="{ 'is-spinning': adminLoading }">↻</span>
          刷新数据
        </button>
      </div>
    </div>

    <div v-if="!adminSummary && adminLoading" class="admin-skeleton" aria-hidden="true">
      <div class="admin-skeleton__row" />
      <div class="admin-skeleton__grid">
        <div class="admin-skeleton__block" />
        <div class="admin-skeleton__block" />
        <div class="admin-skeleton__block" />
        <div class="admin-skeleton__block" />
      </div>
    </div>

    <template v-else-if="adminSummary">
      <!-- KPI strip -->
      <section class="admin-kpi" aria-label="关键指标">
        <div
          v-for="(kpi, index) in kpiItems"
          :key="kpi.label"
          class="admin-kpi__item"
          :style="{ '--delay': `${index * 60}ms` }"
        >
          <p class="admin-kpi__label">{{ kpi.label }}</p>
          <p class="admin-kpi__value">{{ kpi.value }}</p>
          <p class="admin-kpi__hint">{{ kpi.hint }}</p>
        </div>
      </section>

      <!-- Status + Webhook -->
      <section class="admin-section">
        <div class="admin-section__head">
          <h3>运行状态</h3>
          <p>鉴权、构建与安全策略一览</p>
        </div>

        <div class="admin-status-grid">
          <div
            v-for="item in statusItems"
            :key="item.label"
            class="admin-status"
            :class="`is-${item.tone}`"
          >
            <div class="admin-status__top">
              <span class="admin-status__label">{{ item.label }}</span>
              <span class="admin-status__badge">{{ item.badge }}</span>
            </div>
            <p class="admin-status__value">{{ item.value }}</p>
            <p v-if="item.meta" class="admin-status__meta">{{ item.meta }}</p>
          </div>

          <div class="admin-status admin-status--webhook" :class="webhookEnabled ? 'is-success' : 'is-muted'">
            <div class="admin-status__top">
              <span class="admin-status__label">Webhook</span>
              <span class="admin-status__badge">{{ webhookEnabled ? '启用' : '关闭' }}</span>
            </div>
            <p class="admin-status__value">{{ webhookEnabled ? '事件外推已接通' : '未配置推送' }}</p>
            <button
              type="button"
              class="admin-ghost-btn"
              :disabled="webhookTesting || !webhookEnabled"
              @click="testWebhook"
            >
              {{ webhookTesting ? '发送中…' : '发送测试事件' }}
            </button>
          </div>
        </div>
      </section>

      <!-- Tenant + Quota -->
      <div class="admin-split">
        <section class="admin-section admin-section--fill">
          <div class="admin-section__head">
            <h3>租户监控</h3>
            <p>请求量、错误率与延迟分位</p>
          </div>

          <div v-if="tenantMetrics.length === 0" class="admin-empty">暂无租户指标</div>
          <div v-else class="admin-table-wrap">
            <table class="admin-table">
              <thead>
                <tr>
                  <th>租户</th>
                  <th>请求</th>
                  <th>错误率</th>
                  <th>Avg</th>
                  <th>P95</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="metric in tenantMetrics" :key="metric.tenant">
                  <td>
                    <span class="admin-tenant">{{ metric.tenant }}</span>
                  </td>
                  <td class="is-num">{{ metric.request_count }}</td>
                  <td>
                    <div class="admin-err">
                      <div class="admin-err__track">
                        <div
                          class="admin-err__fill"
                          :style="{ width: `${Math.min(metric.error_rate * 100, 100)}%` }"
                          :class="{ 'is-hot': metric.error_rate > 0.05 }"
                        />
                      </div>
                      <span class="is-num">{{ (metric.error_rate * 100).toFixed(1) }}%</span>
                    </div>
                  </td>
                  <td class="is-num">{{ formatMs(metric.avg_latency_ms) }}</td>
                  <td class="is-num">{{ formatMs(metric.p95_latency_ms) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="admin-section">
          <div class="admin-section__head">
            <h3>配额与成本</h3>
            <p>当前租户日用量快照</p>
          </div>

          <div v-if="!quotaUsage" class="admin-empty">暂无配额数据</div>
          <div v-else class="admin-quota">
            <div v-for="row in quotaRows" :key="row.label" class="admin-quota__row">
              <div class="admin-quota__meta">
                <span>{{ row.label }}</span>
                <span class="is-num">{{ row.display }}</span>
              </div>
              <div class="admin-quota__track">
                <div
                  class="admin-quota__fill"
                  :style="{ width: `${row.pct}%` }"
                  :class="{ 'is-warn': row.pct >= 80, 'is-danger': row.pct >= 95 }"
                />
              </div>
            </div>
            <p v-if="auditLogPath" class="admin-footnote">
              审计日志 · <code>{{ auditLogPath }}</code>
            </p>
          </div>
        </section>
      </div>

      <!-- Audit -->
      <section class="admin-section">
        <div class="admin-section__head">
          <h3>最近审计事件</h3>
          <p>关键管理与观测操作留痕</p>
        </div>

        <div v-if="auditEvents.length === 0" class="admin-empty">暂无审计数据</div>
        <ol v-else class="admin-audit">
          <li
            v-for="event in auditEvents"
            :key="`${event.timestamp}-${event.action}-${event.request_id}`"
            class="admin-audit__item"
          >
            <div class="admin-audit__rail" aria-hidden="true" />
            <div class="admin-audit__body">
              <div class="admin-audit__top">
                <code class="admin-audit__action">{{ event.action }}</code>
                <span
                  class="admin-audit__outcome"
                  :class="outcomeClass(event.outcome)"
                >
                  {{ event.outcome || 'unknown' }}
                </span>
              </div>
              <div class="admin-audit__meta">
                <span>{{ event.actor_name || 'system' }}</span>
                <span class="admin-dot">·</span>
                <span>{{ event.resource || '-' }}</span>
                <span class="admin-dot">·</span>
                <time>{{ formatAuditTime(event.timestamp) }}</time>
              </div>
            </div>
          </li>
        </ol>
      </section>
    </template>

    <div v-else class="admin-empty admin-empty--page">
      无法加载管理数据，请检查权限或点击刷新重试。
    </div>
  </div>
</template>

<script>
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { API_BASE, authHeaders } from '../utils/api'
import { loadAuthState, useAuthState } from '../stores/auth'

export default {
  name: 'AdminView',
  data() {
    return {
      auth: useAuthState(),
      adminLoading: false,
      adminSummary: null,
      auditEvents: [],
      tenantMetrics: [],
      webhookStatus: null,
      webhookTesting: false,
      lastSyncedAt: ''
    }
  },
  computed: {
    monitoring() {
      return this.adminSummary?.monitoring || {}
    },
    webhookEnabled() {
      return !!(this.webhookStatus?.enabled ?? this.adminSummary?.webhook?.enabled)
    },
    quotaUsage() {
      return this.adminSummary?.quota?.usage || null
    },
    quotaLimits() {
      return this.adminSummary?.quota?.limits || {}
    },
    auditLogPath() {
      return this.adminSummary?.audit?.log_path || ''
    },
    kpiItems() {
      const m = this.monitoring
      return [
        {
          label: '近一小时查询',
          value: this.displayValue(m.queries_last_hour),
          hint: 'Query volume'
        },
        {
          label: '成功率',
          value: this.displayValue(m.overall_success_rate),
          hint: 'Overall success'
        },
        {
          label: '平均耗时',
          value: this.displayValue(m.avg_response_time_last_hour),
          hint: 'Avg latency'
        },
        {
          label: '工具调用',
          value: this.displayValue(m.total_tool_calls ?? 0),
          hint: 'Tool calls'
        }
      ]
    },
    statusItems() {
      const s = this.adminSummary || {}
      const authOn = !!s.auth?.enabled
      const user = s.auth?.current_user?.username || 'anonymous'
      const build = s.build?.status || 'idle'
      const security = s.security || {}
      const retention = s.retention || {}

      return [
        {
          label: '鉴权',
          badge: authOn ? '启用' : '关闭',
          value: user,
          meta: authOn ? `角色 ${s.auth?.current_user?.role || '-'}` : '开发态匿名访问',
          tone: authOn ? 'success' : 'warn'
        },
        {
          label: '构建',
          badge: build,
          value: build === 'idle' ? '空闲待命' : build,
          meta: s.tenant_id ? `租户 ${s.tenant_id}` : '',
          tone: build === 'processing' ? 'info' : 'neutral'
        },
        {
          label: '安全策略',
          badge: `${security.policy_count ?? 0} 条`,
          value: [
            security.pii_redaction_enabled ? 'PII' : null,
            security.abac_enabled ? 'ABAC' : null,
            security.guardrails_enabled ? '护栏' : null
          ].filter(Boolean).join(' · ') || '未启用',
          meta: '输出脱敏与访问控制',
          tone: security.abac_enabled || security.pii_redaction_enabled ? 'success' : 'muted'
        },
        {
          label: '数据保留',
          badge: retention.enabled ? '启用' : '关闭',
          value: retention.retention_days
            ? `${retention.retention_days} 天`
            : (retention.enabled ? '按策略清理' : '未配置'),
          meta: '会话 / Trace / 审计裁剪',
          tone: retention.enabled ? 'info' : 'muted'
        }
      ]
    },
    quotaRows() {
      const usage = this.quotaUsage || {}
      const limits = this.quotaLimits || {}
      const rows = [
        {
          label: '查询次数',
          used: Number(usage.query_count ?? 0),
          limit: Number(limits.daily_queries ?? 0)
        },
        {
          label: 'Token',
          used: Number(usage.estimated_tokens ?? 0),
          limit: Number(limits.daily_tokens ?? 0)
        },
        {
          label: '估算成本 (USD)',
          used: Number(usage.estimated_cost_usd ?? 0),
          limit: Number(limits.daily_cost_usd ?? 0),
          money: true
        }
      ]
      return rows.map((row) => {
        const pct = row.limit > 0 ? Math.min(100, Math.round((row.used / row.limit) * 100)) : 0
        const usedText = row.money ? row.used.toFixed(4) : this.formatNumber(row.used)
        const limitText = row.limit > 0
          ? (row.money ? row.limit.toFixed(2) : this.formatNumber(row.limit))
          : '∞'
        return {
          label: row.label,
          pct,
          display: `${usedText} / ${limitText}`
        }
      })
    }
  },
  mounted() {
    loadAuthState()
    this.loadAdminConsole()
  },
  methods: {
    async loadAdminConsole() {
      this.adminLoading = true
      try {
        const headers = authHeaders()
        const [summaryRes, auditRes, tenantRes, webhookRes] = await Promise.all([
          axios.get(`${API_BASE}/admin/summary`, { headers }),
          axios.get(`${API_BASE}/admin/audit-events`, { headers }),
          axios.get(`${API_BASE}/admin/tenant-metrics`, { headers }),
          axios.get(`${API_BASE}/admin/webhooks`, { headers }).catch(() => ({ data: null }))
        ])
        this.adminSummary = summaryRes.data
        this.auditEvents = auditRes.data.events || []
        const tenants = tenantRes.data.tenants || {}
        this.tenantMetrics = Object.entries(tenants).map(([tenant, value]) => ({ tenant, ...value }))
        this.webhookStatus = webhookRes.data || summaryRes.data?.webhook || { enabled: false }
        this.lastSyncedAt = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      } catch (e) {
        ElMessage.error(`加载管理台失败: ${e.response?.data?.detail || e.message}`)
      } finally {
        this.adminLoading = false
      }
    },
    async testWebhook() {
      this.webhookTesting = true
      try {
        await axios.post(`${API_BASE}/admin/webhooks/test`, {}, { headers: authHeaders() })
        ElMessage.success('Webhook 测试已发送')
        await this.loadAdminConsole()
      } catch (e) {
        ElMessage.error(`Webhook 测试失败: ${e.response?.data?.detail || e.message}`)
      } finally {
        this.webhookTesting = false
      }
    },
    displayValue(value) {
      if (value === null || value === undefined || value === '' || value === 'N/A') return '—'
      return value
    },
    formatMs(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
      const n = Number(value)
      if (n >= 1000) return `${(n / 1000).toFixed(2)}s`
      return `${Math.round(n)}ms`
    },
    formatNumber(value) {
      return Number(value || 0).toLocaleString('zh-CN')
    },
    formatAuditTime(timestamp) {
      if (!timestamp) return ''
      return new Date(timestamp).toLocaleString('zh-CN')
    },
    outcomeClass(outcome) {
      const text = String(outcome || '').toLowerCase()
      if (text.includes('success') || text.includes('ok')) return 'is-success'
      if (text.includes('fail') || text.includes('error') || text.includes('deny')) return 'is-danger'
      return 'is-muted'
    }
  }
}
</script>

<style scoped>
.admin-console {
  max-width: none;
}

.admin-hero {
  align-items: flex-end;
  margin-bottom: 28px;
}

.admin-hero__actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.admin-live {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-glass);
  color: var(--text-secondary);
  font-size: 12px;
  backdrop-filter: var(--glass-blur);
}

.admin-live__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--success);
  box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.45);
  animation: adminPulse 2s ease-out infinite;
}

.admin-live.is-loading .admin-live__dot {
  background: var(--warning);
  animation: none;
}

.admin-live__time {
  color: var(--text-muted);
}

.admin-refresh {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 16px;
  border: none;
  border-radius: 12px;
  background: var(--gradient-primary);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: var(--shadow-md);
  transition: transform var(--transition-fast), box-shadow var(--transition-fast), opacity var(--transition-fast);
}

.admin-refresh:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: var(--shadow-lg);
}

.admin-refresh:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.admin-refresh__icon {
  display: inline-block;
  font-size: 15px;
  line-height: 1;
}

.admin-refresh__icon.is-spinning {
  animation: adminSpin 0.8s linear infinite;
}

.admin-kpi {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 28px;
}

.admin-kpi__item {
  position: relative;
  padding: 18px 18px 16px;
  border-radius: 18px;
  border: 1px solid var(--border-color);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.55), rgba(255, 255, 255, 0.28)),
    var(--bg-glass);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  animation: adminRise 0.45s ease both;
  animation-delay: var(--delay);
}

.admin-kpi__item::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: var(--gradient-primary);
  opacity: 0.85;
}

.admin-kpi__label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.admin-kpi__value {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--text-primary);
  line-height: 1.1;
  margin-bottom: 6px;
}

.admin-kpi__hint {
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.admin-section {
  margin-bottom: 24px;
  padding: 20px 22px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: var(--bg-glass);
  backdrop-filter: var(--glass-blur);
  box-shadow: var(--shadow-sm);
}

.admin-section__head {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 16px;
}

.admin-section__head h3 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.admin-section__head p {
  font-size: 13px;
  color: var(--text-muted);
}

.admin-status-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.admin-status {
  padding: 14px 14px 12px;
  border-radius: 14px;
  border: 1px solid var(--border-light);
  background: rgba(148, 163, 184, 0.06);
  min-height: 118px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.admin-status.is-success {
  background: rgba(16, 185, 129, 0.08);
  border-color: rgba(16, 185, 129, 0.18);
}

.admin-status.is-warn {
  background: rgba(245, 158, 11, 0.1);
  border-color: rgba(245, 158, 11, 0.2);
}

.admin-status.is-info {
  background: rgba(6, 182, 212, 0.08);
  border-color: rgba(6, 182, 212, 0.18);
}

.admin-status.is-muted,
.admin-status.is-neutral {
  background: rgba(148, 163, 184, 0.06);
}

.admin-status__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.admin-status__label {
  font-size: 12px;
  color: var(--text-muted);
}

.admin-status__badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.55);
  color: var(--text-secondary);
  border: 1px solid var(--border-light);
}

.admin-status__value {
  font-size: 15px;
  font-weight: 650;
  color: var(--text-primary);
  line-height: 1.35;
}

.admin-status__meta {
  margin-top: auto;
  font-size: 12px;
  color: var(--text-muted);
}

.admin-ghost-btn {
  margin-top: auto;
  align-self: flex-start;
  height: 30px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast);
}

.admin-ghost-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.08);
  border-color: rgba(99, 102, 241, 0.25);
  color: var(--primary-dark);
}

.admin-ghost-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.admin-split {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(260px, 0.85fr);
  gap: 16px;
  margin-bottom: 8px;
}

.admin-section--fill {
  min-width: 0;
}

.admin-table-wrap {
  overflow-x: auto;
}

.admin-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.admin-table th {
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
  padding: 0 10px 10px 0;
  border-bottom: 1px solid var(--border-color);
}

.admin-table td {
  padding: 12px 10px 12px 0;
  border-bottom: 1px solid var(--border-light);
  color: var(--text-secondary);
  vertical-align: middle;
}

.admin-table tbody tr:last-child td {
  border-bottom: none;
}

.admin-table .is-num,
.is-num {
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum';
}

.admin-tenant {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 10px;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.08);
  color: var(--primary-dark);
  font-weight: 600;
  font-size: 12px;
}

.admin-err {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 110px;
}

.admin-err__track,
.admin-quota__track {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.18);
  overflow: hidden;
}

.admin-err__fill,
.admin-quota__fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #34d399, #10b981);
  transition: width 0.45s ease;
}

.admin-err__fill.is-hot,
.admin-quota__fill.is-danger {
  background: linear-gradient(90deg, #fb7185, #ef4444);
}

.admin-quota__fill.is-warn {
  background: linear-gradient(90deg, #fbbf24, #f59e0b);
}

.admin-quota {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.admin-quota__row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.admin-quota__meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}

.admin-footnote {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-muted);
  word-break: break-all;
}

.admin-footnote code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  color: var(--text-secondary);
}

.admin-audit {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.admin-audit__item {
  position: relative;
  display: grid;
  grid-template-columns: 16px 1fr;
  gap: 12px;
  padding: 12px 0;
}

.admin-audit__item + .admin-audit__item {
  border-top: 1px solid var(--border-light);
}

.admin-audit__rail {
  position: relative;
  width: 10px;
  margin-top: 6px;
}

.admin-audit__rail::before {
  content: '';
  position: absolute;
  left: 3px;
  top: 0;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary);
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.12);
}

.admin-audit__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.admin-audit__action {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  background: transparent;
}

.admin-audit__outcome {
  font-size: 11px;
  font-weight: 700;
  text-transform: lowercase;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid var(--border-light);
}

.admin-audit__outcome.is-success {
  color: #047857;
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.2);
}

.admin-audit__outcome.is-danger {
  color: #b91c1c;
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.2);
}

.admin-audit__outcome.is-muted {
  color: var(--text-muted);
  background: rgba(148, 163, 184, 0.1);
}

.admin-audit__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}

.admin-dot {
  opacity: 0.5;
}

.admin-empty {
  padding: 24px 8px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}

.admin-empty--page {
  margin-top: 40px;
  padding: 48px 16px;
  border: 1px dashed var(--border-color);
  border-radius: 16px;
}

.admin-skeleton__row {
  height: 88px;
  border-radius: 18px;
  margin-bottom: 16px;
  background: linear-gradient(90deg, rgba(148, 163, 184, 0.12), rgba(148, 163, 184, 0.22), rgba(148, 163, 184, 0.12));
  background-size: 200% 100%;
  animation: adminShimmer 1.2s linear infinite;
}

.admin-skeleton__grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.admin-skeleton__block {
  height: 110px;
  border-radius: 16px;
  background: linear-gradient(90deg, rgba(148, 163, 184, 0.1), rgba(148, 163, 184, 0.2), rgba(148, 163, 184, 0.1));
  background-size: 200% 100%;
  animation: adminShimmer 1.2s linear infinite;
}

:global(.dark) .admin-kpi__item {
  background:
    linear-gradient(180deg, rgba(129, 140, 248, 0.08), rgba(255, 255, 255, 0.02)),
    var(--bg-glass);
}

:global(.dark) .admin-status__badge {
  background: rgba(15, 15, 26, 0.45);
}

:global(.dark) .admin-tenant {
  background: rgba(129, 140, 248, 0.14);
  color: var(--primary-light);
}

:global(.dark) .admin-ghost-btn:hover:not(:disabled) {
  color: var(--primary-light);
}

@keyframes adminRise {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes adminPulse {
  0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.45); }
  70% { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
  100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}

@keyframes adminSpin {
  to { transform: rotate(360deg); }
}

@keyframes adminShimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

@media (max-width: 1100px) {
  .admin-status-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .admin-kpi {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .admin-split {
    grid-template-columns: 1fr;
  }

  .admin-hero {
    flex-direction: column;
    align-items: stretch;
  }

  .admin-hero__actions {
    justify-content: space-between;
  }
}

@media (max-width: 640px) {
  .admin-kpi {
    grid-template-columns: 1fr;
  }

  .admin-status-grid {
    grid-template-columns: 1fr;
  }

  .admin-kpi__value {
    font-size: 24px;
  }

  .admin-audit__top {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
