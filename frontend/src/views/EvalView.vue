<template>
  <div class="page-shell">
    <div class="page-hero">
      <div>
        <p class="page-eyebrow">RAG Evaluation</p>
        <h2 class="page-title">RAG 评测回测</h2>
        <p class="page-desc">对比 vector / bm25 / hybrid 检索策略。勾选 Rerank 会额外评测 hybrid+rerank。</p>
      </div>
    </div>

    <div class="eval-panel page-panel page-card">
      <el-checkbox v-model="evalIncludeRerank" :disabled="evalLoading" style="margin-bottom:12px">
        包含 Rerank 对比（仅 hybrid）
      </el-checkbox>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <el-button type="primary" :loading="evalLoading" style="flex:1;min-width:140px" @click="runBacktest">
          {{ evalLoading ? evalProgressText : '标准回测' }}
        </el-button>
        <el-button type="success" :loading="evalLoading" style="flex:1;min-width:140px" @click="runEnterpriseBacktest">
          企业回测
        </el-button>
      </div>

      <div v-if="evalLoading && evalPhase === 'loading_rerank'" class="rerank-download-box">
        <div class="rerank-download-title">正在准备 Rerank 模型</div>
        <div class="rerank-download-model">{{ downloadModel }}</div>
        <el-progress
          :percentage="downloadPercent"
          :stroke-width="12"
          :status="downloadPhase === 'ready' ? 'success' : undefined"
          style="margin-top:10px"
        />
        <p class="rerank-download-msg">{{ downloadMessage }}</p>
        <p v-if="downloadBytesText" class="rerank-download-bytes">{{ downloadBytesText }}</p>
        <p class="rerank-download-hint">首次下载约 2GB，完成后会缓存；取消勾选 Rerank 可跳过此步骤。</p>
      </div>

      <el-progress
        v-else-if="evalLoading && evalProgressTotal > 0"
        :percentage="Math.round((evalProgress / evalProgressTotal) * 100)"
        :stroke-width="10"
        style="margin-top:12px"
      />

      <div v-if="enterpriseEvalReport" class="eval-results">
        <h4>
          企业门禁:
          <span :style="{ color: enterpriseEvalReport.release_gates?.approved ? '#67c23a' : '#f56c6c' }">
            {{ enterpriseEvalReport.release_gates?.approved ? '允许上线' : '暂不允许上线' }}
          </span>
        </h4>
        <p>
          命中率门槛: {{ (enterpriseEvalReport.release_gates?.min_hit_rate || 0) * 100 }}% /
          护栏通过率门槛: {{ (enterpriseEvalReport.release_gates?.min_guardrail_pass_rate || 0) * 100 }}%
        </p>
        <p>
          最佳策略: {{ enterpriseEvalReport.retrieval?.best_strategy || '-' }}，
          护栏通过率: {{ ((enterpriseEvalReport.guardrails?.pass_rate || 0) * 100).toFixed(1) }}%
        </p>
      </div>

      <div v-if="evalReport" class="eval-results">
        <h4>最佳策略: {{ evalReport.best_strategy }}</h4>
        <el-table :data="evalTableData" size="small" stripe>
          <el-table-column prop="strategy" label="策略" />
          <el-table-column prop="hit_rate" label="Hit Rate" />
          <el-table-column prop="recall" label="Recall@K" />
          <el-table-column prop="mrr" label="MRR" />
          <el-table-column prop="latency" label="延迟(ms)" />
        </el-table>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { API_BASE } from '../utils/api'

export default {
  name: 'EvalView',
  data() {
    return {
      evalLoading: false,
      evalProgress: 0,
      evalProgressTotal: 0,
      evalCurrentStrategy: '',
      evalPhase: '',
      evalIncludeRerank: false,
      evalReport: null,
      enterpriseEvalReport: null,
      evalDownload: null
    }
  },
  computed: {
    downloadModel() {
      return this.evalDownload?.model || this.evalCurrentStrategy || 'BAAI/bge-reranker-v2-m3'
    },
    downloadPhase() {
      return this.evalDownload?.phase || ''
    },
    downloadPercent() {
      const p = Number(this.evalDownload?.percent)
      if (Number.isFinite(p) && p > 0) return Math.min(100, Math.round(p))
      if (this.downloadPhase === 'loading' || this.downloadPhase === 'ready') return 100
      return 0
    },
    downloadMessage() {
      if (this.evalDownload?.message) return this.evalDownload.message
      if (this.downloadPhase === 'loading') return '下载完成，正在加载到内存…'
      return '正在连接模型仓库并准备下载…'
    },
    downloadBytesText() {
      const d = this.evalDownload
      if (!d) return ''
      const cur = Number(d.downloaded_bytes || 0)
      const total = Number(d.total_bytes || 0)
      if (!cur && !total) return ''
      const fmt = (n) => {
        if (n >= 1024 * 1024 * 1024) return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`
        if (n >= 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`
        if (n >= 1024) return `${(n / 1024).toFixed(1)} KB`
        return `${n} B`
      }
      return total > 0 ? `${fmt(cur)} / ${fmt(total)}` : `已下载 ${fmt(cur)}`
    },
    evalProgressText() {
      if (this.evalPhase === 'loading_rerank') {
        if (this.downloadPercent > 0) return `下载 Rerank ${this.downloadPercent}%`
        if (this.downloadPhase === 'loading') return '加载 Rerank 到内存…'
        return '下载 Rerank 模型中…'
      }
      if (this.evalProgressTotal > 0) {
        const pct = Math.round((this.evalProgress / this.evalProgressTotal) * 100)
        const strategy = this.evalCurrentStrategy ? ` (${this.evalCurrentStrategy})` : ''
        return `回测中 ${pct}%${strategy}`
      }
      if (this.evalCurrentStrategy) return `评测中: ${this.evalCurrentStrategy}`
      return '回测启动中...'
    },
    evalTableData() {
      // 后端报告结构：summary 为策略汇总指标，results 为逐条用例明细
      if (!this.evalReport?.summary) return []
      return Object.entries(this.evalReport.summary).map(([strategy, stats]) => ({
        strategy,
        hit_rate: this.fmt(stats.hit_rate),
        recall: this.fmt(stats.avg_recall_at_k ?? stats.recall_at_k),
        mrr: stats.avg_mrr != null ? Number(stats.avg_mrr).toFixed(3) : this.fmt(stats.mrr),
        latency: stats.avg_latency_ms != null
          ? Number(stats.avg_latency_ms).toFixed(0)
          : (stats.latency ?? '-')
      }))
    }
  },
  methods: {
    fmt(v) {
      if (v == null) return '-'
      return typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : v
    },
    applyStatus(status) {
      this.evalProgress = status.progress || 0
      this.evalProgressTotal = status.total || 0
      this.evalCurrentStrategy = status.current_strategy || ''
      this.evalPhase = status.phase || ''
      this.evalDownload = status.download || null
    },
    async runBacktest() {
      this.evalLoading = true
      this.evalProgress = 0
      this.evalProgressTotal = 0
      this.evalCurrentStrategy = ''
      this.evalPhase = ''
      this.evalDownload = null
      this.evalReport = null
      try {
        const rerankOptions = this.evalIncludeRerank ? [false, true] : [false]
        await axios.post(`${API_BASE}/eval/backtest-async`, {
          dataset_path: 'data/demo_dataset/qa_pairs.json',
          methods: ['vector', 'bm25', 'hybrid'],
          rerank_options: rerankOptions
        })
        const poll = async () => {
          const res = await axios.get(`${API_BASE}/eval/backtest-status`)
          this.applyStatus(res.data)
          if (res.data.running) {
            await new Promise((r) => setTimeout(r, 1000))
            return poll()
          }
          if (res.data.result?.error) throw new Error(res.data.result.error)
          this.evalReport = res.data.result
        }
        await poll()
        ElMessage.success(`回测完成，最佳策略: ${this.evalReport.best_strategy}`)
      } catch (e) {
        ElMessage.error(`回测失败: ${e.response?.data?.detail || e.message}`)
      } finally {
        this.evalLoading = false
        this.evalDownload = null
      }
    },
    async runEnterpriseBacktest() {
      this.evalLoading = true
      this.evalProgress = 0
      this.evalProgressTotal = 0
      this.evalCurrentStrategy = ''
      this.evalPhase = ''
      this.evalDownload = null
      try {
        const rerankOptions = this.evalIncludeRerank ? [false, true] : [false]
        await axios.post(`${API_BASE}/eval/enterprise-backtest-async`, {
          dataset_path: 'data/demo_dataset/qa_pairs.json',
          methods: ['vector', 'bm25', 'hybrid'],
          rerank_options: rerankOptions
        })
        const poll = async () => {
          const res = await axios.get(`${API_BASE}/eval/enterprise-backtest-status`)
          this.applyStatus(res.data)
          if (res.data.running) {
            await new Promise((r) => setTimeout(r, 1000))
            return poll()
          }
          if (res.data.result?.error) throw new Error(res.data.result.error)
          this.enterpriseEvalReport = res.data.result
        }
        await poll()
        ElMessage.success(this.enterpriseEvalReport?.release_gates?.approved ? '企业回测通过' : '企业回测未通过门禁')
      } catch (e) {
        ElMessage.error(`企业回测失败: ${e.response?.data?.detail || e.message}`)
      } finally {
        this.evalLoading = false
        this.evalDownload = null
      }
    }
  }
}
</script>

<style scoped>
.rerank-download-box {
  margin-top: 14px;
  padding: 14px 16px;
  border-radius: 10px;
  background: linear-gradient(180deg, #f5f8ff 0%, #eef3ff 100%);
  border: 1px solid #d9e4ff;
}
.rerank-download-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}
.rerank-download-model {
  margin-top: 4px;
  font-size: 12px;
  color: #5b6cff;
  word-break: break-all;
}
.rerank-download-msg {
  margin: 10px 0 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}
.rerank-download-bytes {
  margin: 4px 0 0;
  font-size: 12px;
  color: #409eff;
  font-variant-numeric: tabular-nums;
}
.rerank-download-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
</style>
