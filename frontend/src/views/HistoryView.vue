<template>
  <div class="page-shell">
    <div class="page-hero">
      <div>
        <p class="page-eyebrow">Conversation History</p>
        <h2 class="page-title">对话历史</h2>
        <p class="page-desc">查看、继续或删除历史会话。</p>
      </div>
      <el-button type="primary" :loading="historyLoading" @click="loadConversationList">刷新</el-button>
    </div>

    <div class="page-panel page-card">
      <div v-if="historyLoading" class="history-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>加载中...</span>
      </div>

      <div v-else-if="conversationList.length === 0" class="history-empty">
        <div class="empty-icon">💬</div>
        <p>暂无对话历史</p>
      </div>

      <div v-else class="conversation-list history-page-list">
        <div
          v-for="conv in conversationList"
          :key="conv.id"
          class="conversation-item"
          @click="openConversation(conv.id)"
        >
          <div class="conv-header">
            <span class="conv-title">{{ conv.title }}</span>
            <el-button type="text" size="small" class="delete-btn" title="删除对话" @click.stop="deleteConversation(conv.id)">
              🗑️
            </el-button>
          </div>
          <div class="conv-meta">
            <span class="conv-count">{{ conv.message_count }} 条消息</span>
            <span class="conv-time">{{ formatTime(conv.last_time) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { API_BASE, authHeaders } from '../utils/api'

export default {
  name: 'HistoryView',
  components: { Loading },
  data() {
    return {
      conversationList: [],
      historyLoading: false
    }
  },
  mounted() {
    this.loadConversationList()
  },
  methods: {
    async loadConversationList() {
      this.historyLoading = true
      try {
        const res = await axios.get(`${API_BASE}/conversations`, { headers: authHeaders() })
        if (res.data.success) this.conversationList = res.data.conversations
      } catch {
        ElMessage.error('加载对话列表失败')
      } finally {
        this.historyLoading = false
      }
    },
    openConversation(id) {
      this.$router.push({ name: 'chat', query: { c: id } })
    },
    async deleteConversation(conversationId) {
      try {
        await ElMessageBox.confirm('确定要删除这个对话吗？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        const res = await axios.delete(`${API_BASE}/conversations/${conversationId}`, { headers: authHeaders() })
        if (res.data.success) {
          this.conversationList = this.conversationList.filter((c) => c.id !== conversationId)
          ElMessage.success('对话已删除')
        }
      } catch (e) {
        if (e !== 'cancel') ElMessage.error('删除对话失败')
      }
    },
    formatTime(timestamp) {
      if (!timestamp) return ''
      const date = new Date(timestamp)
      const now = new Date()
      const diff = now - date
      if (diff < 24 * 60 * 60 * 1000 && date.getDate() === now.getDate()) {
        return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      }
      if (diff < 7 * 24 * 60 * 60 * 1000) {
        return ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][date.getDay()]
      }
      return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
    }
  }
}
</script>
