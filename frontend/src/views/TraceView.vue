<template>
  <div class="page-shell">
    <div class="page-hero">
      <div>
        <p class="page-eyebrow">Agent Traces</p>
        <h2 class="page-title">Agent 追踪</h2>
        <p class="page-desc">查看 Agent 推理轨迹、工具调用与耗时明细。</p>
      </div>
      <el-button type="primary" @click="loadTraces">刷新</el-button>
    </div>

    <div class="trace-panel page-panel page-grid-2">
      <section class="page-card">
        <div v-if="traceList.length === 0" class="admin-muted">暂无追踪记录</div>
        <div
          v-for="t in traceList"
          :key="t.trace_id"
          class="trace-item"
          :class="{ active: traceDetail?.trace_id === t.trace_id }"
          @click="loadTraceDetail(t.trace_id)"
        >
          <div class="trace-q">{{ t.question }}</div>
          <div class="trace-meta">
            <span>{{ t.mode }}</span>
            <span>{{ t.total_duration_ms }}ms</span>
            <span>{{ t.step_count }} 步</span>
            <el-tag :type="t.success ? 'success' : 'danger'" size="small">
              {{ t.success ? '成功' : '失败' }}
            </el-tag>
          </div>
        </div>
      </section>

      <section class="page-card">
        <div v-if="!traceDetail" class="admin-muted">选择左侧记录查看推理步骤</div>
        <div v-else class="trace-detail">
          <h4>推理步骤</h4>
          <div v-for="step in traceDetail.steps" :key="step.step" class="trace-step">
            <span class="trace-step-type">{{ step.type }}</span>
            <span v-if="step.tool" class="trace-step-tool">{{ step.tool }}</span>
            <div class="trace-step-content">{{ step.content }}</div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { API_BASE } from '../utils/api'

export default {
  name: 'TraceView',
  data() {
    return {
      traceList: [],
      traceDetail: null
    }
  },
  mounted() {
    this.loadTraces()
  },
  methods: {
    async loadTraces() {
      try {
        const res = await axios.get(`${API_BASE}/traces`)
        this.traceList = res.data.traces || []
      } catch {
        ElMessage.error('加载追踪失败')
      }
    },
    async loadTraceDetail(traceId) {
      try {
        const res = await axios.get(`${API_BASE}/traces/${traceId}`)
        this.traceDetail = res.data
      } catch {
        ElMessage.error('加载追踪详情失败')
      }
    }
  }
}
</script>
