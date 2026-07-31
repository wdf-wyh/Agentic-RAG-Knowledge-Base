<template>
  <div class="chat-page">
    <!-- 主聊天区域 -->
      <main class="chat-area">
        <div class="messages-container">
          <div v-if="messages.length === 0" class="empty-state">
            <div class="hero-badge">Local-first Agentic Knowledge Base</div>
            <div class="empty-icon floating">🚀</div>
            <h2>把文档变成可对话的知识系统</h2>
            <p class="hero-subtitle">{{ heroDescription }}</p>

            <div class="hero-actions">
              <el-button type="primary" class="hero-primary-btn" @click="$router.push('/knowledge')">
                上传并构建知识库
              </el-button>
              <el-button class="hero-secondary-btn" @click="$router.push('/settings')">
                配置模型
              </el-button>
            </div>

            <div class="hero-status-grid">
              <div class="hero-status-card glass-card">
                <span class="hero-status-label">知识库状态</span>
                <span :class="['hero-status-value', status.vector_store_loaded ? 'is-ready' : 'is-empty']">
                  {{ knowledgeBaseStatus }}
                </span>
              </div>
              <div class="hero-status-card glass-card">
                <span class="hero-status-label">当前模式</span>
                <span class="hero-status-value">{{ currentModeLabel }}</span>
              </div>
              <div class="hero-status-card glass-card">
                <span class="hero-status-label">模型提供者</span>
                <span class="hero-status-value">{{ currentProviderLabel }}</span>
              </div>
            </div>

            <div class="hero-scenarios">
              <div class="hero-scenario-card glass-card hover-lift">
                <span class="hero-scenario-icon">📚</span>
                <div>
                  <h3>知识库问答</h3>
                  <p>上传 PDF、Markdown、TXT 后，快速获得有来源的回答。</p>
                </div>
              </div>
              <div class="hero-scenario-card glass-card hover-lift">
                <span class="hero-scenario-icon">🧠</span>
                <div>
                  <h3>智能推理</h3>
                  <p>让 Agent 自动选择检索、文件操作和联网工具完成复杂任务。</p>
                </div>
              </div>
              <div class="hero-scenario-card glass-card hover-lift">
                <span class="hero-scenario-icon">🏢</span>
                <div>
                  <h3>本地优先部署</h3>
                  <p>兼容 Ollama、本地知识库和私有化部署场景，适合中文团队内部使用。</p>
                </div>
              </div>
            </div>

            <div class="hero-quickstart glass-card">
              <div class="hero-section-title">三步开始</div>
              <div class="hero-steps">
                <div class="hero-step">
                  <span class="hero-step-index">1</span>
                  <span>在“设置”中选择可用模型提供者</span>
                </div>
                <div class="hero-step">
                  <span class="hero-step-index">2</span>
                  <span>上传文档并点击“开始构建”</span>
                </div>
                <div class="hero-step">
                  <span class="hero-step-index">3</span>
                  <span>从下面的示例问题开始体验</span>
                </div>
              </div>
            </div>

            <div class="hero-prompts glass-card">
              <div class="hero-section-title">示例问题</div>
              <div class="hero-prompt-list">
                <button
                  v-for="prompt in starterPrompts"
                  :key="prompt"
                  type="button"
                  class="hero-prompt-chip"
                  @click="applyStarterPrompt(prompt)"
                >
                  {{ prompt }}
                </button>
              </div>
            </div>
          </div>

          <div v-for="(msg, idx) in messages" :key="idx" :class="['message', msg.role, { 'error-message': msg.isError }]">
            <div class="message-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
            <div class="message-content-wrapper">
              <!-- GPT 风格：推理过程在回答上方 -->
              <div
                v-if="msg.role === 'assistant' && showReasoningBlock(msg)"
                class="reasoning-block"
              >
                <button
                  type="button"
                  class="reasoning-toggle"
                  :aria-expanded="isReasoningOpen(msg)"
                  @click="toggleReasoning(idx)"
                >
                  <span class="reasoning-chevron" :class="{ open: isReasoningOpen(msg) }">▾</span>
                  <span class="reasoning-label" :class="{ thinking: isMessageThinking(msg) }">
                    {{ reasoningLabel(msg) }}
                  </span>
                </button>
                <div v-show="isReasoningOpen(msg)" class="reasoning-panel">
                  <div
                    v-if="!msg.thoughtProcess || msg.thoughtProcess.length === 0"
                    class="reasoning-step"
                  >
                    <p class="reasoning-text">
                      <span v-if="isMessageThinking(msg)" class="spinner" aria-hidden="true"></span>
                      正在分析问题…
                    </p>
                  </div>
                  <div
                    v-for="(step, tidx) in msg.thoughtProcess"
                    :key="tidx"
                    class="reasoning-step"
                  >
                    <p class="reasoning-text">{{ step.thought }}</p>
                  </div>
                </div>
              </div>

              <div
                v-if="shouldShowAnswerContent(msg)"
                :class="['message-content', { 'error-content': msg.isError }]"
              >
                <!-- 支持逐字显示效果 -->
                <p v-if="msg.role === 'assistant' && idx === messages.length - 1 && !msg.finished">
                  {{ formatContent(msg.content) }}
                  <span class="spinner" role="status" aria-label="加载中"></span>
                </p>
                <p v-else>{{ formatContent(msg.content) }}</p>

                <!-- 图片显示 -->
                <div v-if="msg.images && msg.images.length > 0" class="message-images">
                  <img 
                    v-for="(image, imgIdx) in msg.images" 
                    :key="imgIdx"
                    :src="image" 
                    :alt="`图片 ${imgIdx + 1}`" 
                  />
                </div>
                <!-- 单图片兼容 -->
                <div v-else-if="msg.image" class="message-images">
                  <img :src="msg.image" :alt="'图片'" />
                </div>

                <!-- 视频显示 -->
                <div v-if="msg.videos && msg.videos.length > 0" class="message-videos">
                  <video 
                    v-for="(video, vidIdx) in msg.videos" 
                    :key="vidIdx"
                    :src="video" 
                    controls
                    playsinline
                    preload="metadata"
                    class="message-video"
                  >
                    您的浏览器不支持视频播放
                  </video>
                </div>
                
                <!-- 文件显示 -->
                <div v-if="msg.files && msg.files.length > 0" class="message-files">
                  <div v-for="(file, fIdx) in msg.files" :key="fIdx" class="message-file-item">
                    <span class="file-icon-small">{{ getFileIcon(file.type) }}</span>
                    <span class="file-name-small">{{ file.name }}</span>
                    <span class="file-size-small">{{ formatFileSize(file.size) }}</span>
                  </div>
                </div>
              </div>

              <!-- 参考来源 -->
              <div v-if="msg.sources && msg.sources.length > 0" class="message-sources">
                <el-collapse>
                  <el-collapse-item title="参考来源" name="sources">
                    <ul class="sources-list">
                      <li v-for="(source, sidx) in msg.sources" :key="sidx" class="source-item" @click="highlightSource(source)">
                        <div class="source-title">
                          {{ source.filename || source.source }}
                          <span v-if="source.page" class="source-page">P{{ source.page }}</span>
                          <span v-if="source.chunk_index != null" class="source-chunk">#{{ source.chunk_index }}</span>
                        </div>
                        <div class="source-preview">{{ source.preview }}</div>
                        <div v-if="source._highlighted" class="source-highlight">{{ source.highlight_text }}</div>
                      </li>
                    </ul>
                  </el-collapse-item>
                </el-collapse>
              </div>
              
            </div>
          </div>
        </div>

        <!-- 输入区域 -->
        <div class="input-container">
          <div class="input-wrapper">
            <div class="input-actions">
              <el-button
                type="text"
                @click="triggerImageInput"
                title="上传图片"
                class="upload-image-btn"
              >
                <span class="upload-icon">+</span>
              </el-button>
              <el-button
                type="text"
                @click="triggerChatFileInput"
                title="上传文件"
                class="upload-file-btn"
              >
                <span class="upload-icon">📁</span>
              </el-button>
              <input
                ref="imageInput"
                type="file"
                accept="image/*"
                multiple
                style="display: none"
                @change="handleImageSelect"
              />
              <input
                ref="fileInput2"
                type="file"
                accept=".pdf,.doc,.docx,.txt,.md,.json,.csv,.xls,.xlsx"
                multiple
                style="display: none"
                @change="handleFileAttach"
              />
            </div>
            <div class="input-box">
              <!-- 图片预览 -->
              <div v-if="uploadedImages.length > 0" class="images-preview-container">
                <div 
                  v-for="(img, idx) in uploadedImages" 
                  :key="idx" 
                  class="image-preview-item"
                >
                  <img :src="img" :alt="`预览图片 ${idx + 1}`" />
                  <el-button
                    type="text"
                    @click="removeImage(idx)"
                    class="remove-image"
                  >
                    ✕
                  </el-button>
                </div>
              </div>
              
              <!-- 文件预览 -->
              <div v-if="attachedFiles && attachedFiles.length > 0" class="files-preview-container">
                <div 
                  v-for="(file, idx) in attachedFiles" 
                  :key="`file-${idx}-${file.name}`" 
                  class="file-preview-item"
                >
                  <span class="file-icon">{{ getFileIcon(file && file.type) }}</span>
                  <div class="file-info">
                    <span class="file-name">{{ file && file.name || '未知文件' }}</span>
                    <span class="file-size">{{ file && file.size ? formatFileSize(file.size) : '' }}</span>
                  </div>
                  <el-button
                    type="text"
                    @click="removeFile(idx)"
                    class="remove-file"
                  >
                    ✕
                  </el-button>
                </div>
              </div>
              <el-input
                ref="chatInput"
                v-model="question"
                type="textarea"
                :rows="3"
                placeholder="输入您的问题... "
                class="chat-input"
                @keydown="handleInputKeydown"
                @paste="handlePaste"
              />
            </div>
            <el-button
              type="primary"
              @click="sendQuestion"
              :loading="messageLoading"
              class="send-btn"
            >
              发送
            </el-button>
          </div>
        </div>
      </main>
  </div>
</template>

<script>
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { authHeaders as sharedAuthHeaders } from '../utils/api'
import { useAuthState, loadAuthState, clearAuthSession } from '../stores/auth'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export default {
  components: { Loading },
  directives: {
    'click-outside': {
      mounted(el, binding) {
        el._clickOutside = (event) => {
          if (!(el === event.target || el.contains(event.target))) {
            binding.value(event)
          }
        }
        document.addEventListener('click', el._clickOutside)
      },
      unmounted(el) {
        document.removeEventListener('click', el._clickOutside)
      }
    }
  },
  data() {
    return {
      Loading,
      // 主题：暗色模式开关
      isDark: false,
      question: '',
      messages: [],
      conversationId: null,  // 当前会话ID
      status: { vector_store_loaded: false },
      settingsVisible: false,
      kbVisible: false,
      historyVisible: false,
      adminVisible: false,
      evalVisible: false,
      traceVisible: false,
      evalLoading: false,
      evalProgress: 0,
      evalProgressTotal: 0,
      evalCurrentStrategy: '',
      evalPhase: '',
      evalIncludeRerank: false,
      evalReport: null,
      enterpriseEvalReport: null,
      evalDownload: null,
      traceList: [],
      traceDetail: null,
      messageLoading: false,
      
      // 对话历史
      conversationList: [],
      historyLoading: false,
      accessToken: '',
      currentUser: null,
      adminLoading: false,
      adminSummary: null,
      auditEvents: [],
      tenantMetrics: [],
      webhookStatus: { enabled: false, events: [], recent: [] },
      webhookTesting: false,
      
      // 查询模式
      queryMode: 'smart',
      modeDropdownOpen: false,
      modeOptions: [
        { value: 'rag', label: '纯 RAG', icon: '📚', desc: '仅知识库检索，速度快' },
        { value: 'smart', label: '智能模式', icon: '🧠', desc: '大模型分析问题，自动选择最佳工具' }
      ],
      
      // 模型提供者选项
      providerDropdownOpen: false,
      providerOptions: [
        { value: '', label: '后端默认' },
        { value: 'openai', label: 'OpenAI' },
        { value: 'gemini', label: 'Gemini' },
        { value: 'ollama', label: 'Ollama (本地)' },
        { value: 'deepseek', label: 'DeepSeek (远程)' }
      ],
      
      // 模型配置
      provider: '',
      ollamaModel: '',
      ollamaApiUrl: '',
      deepseekModel: '',
      deepseekApiUrl: '',
      deepseekApiKey: '',
      
      // 文件上传
      uploadedFiles: [],
      
      // 构建进度
      buildProgress: {
        processing: false,
        progress: 0,
        total: 0,
        current_file: '',
        status: 'idle'
      },
      buildResult: null,
      
      // 构建进度轮询
      progressInterval: null,
      
      // 图片数据
      uploadedImages: [],
      
      // 附件数据
      attachedFiles: [],
      
      // 文件管理
      kbTab: 'upload',
      fileList: [],
      fileListLoading: false,
      editingFile: null,
      fileSaving: false,
      fileSaveMsg: null,
      newFileVisible: false,
      newFileName: '',
      starterPrompts: [
        '请总结这份知识库的核心内容，并给出 3 个关键结论。',
        '根据已有文档，帮我整理一个面向新成员的 5 分钟入门指南。',
        '这个项目支持哪些模型提供者？分别适合什么场景？',
        '如果我要把它部署到团队内部服务器，推荐的最小配置是什么？'
      ]
    }
  },
  computed: {
    progressPercentage() {
      if (this.buildProgress.total === 0) return 0
      return Math.round((this.buildProgress.progress / this.buildProgress.total) * 100)
    },
    progressColor() {
      const percentage = this.progressPercentage
      if (percentage < 30) return '#409eff'
      if (percentage < 70) return '#e6a23c'
      return '#67c23a'
    },
    evalTableData() {
      if (!this.evalReport?.summary) return []
      return Object.entries(this.evalReport.summary).map(([strategy, stats]) => ({
        strategy,
        hit_rate: (stats.hit_rate * 100).toFixed(1) + '%',
        recall: (stats.avg_recall_at_k * 100).toFixed(1) + '%',
        mrr: stats.avg_mrr.toFixed(3),
        latency: stats.avg_latency_ms.toFixed(0),
      }))
    },
    evalProgressText() {
      if (this.evalPhase === 'loading_rerank') {
        const pct = Number(this.evalDownload?.percent)
        if (Number.isFinite(pct) && pct > 0) return `下载 Rerank ${Math.round(pct)}%`
        if (this.evalDownload?.phase === 'loading') return '加载 Rerank 到内存…'
        if (this.evalDownload?.message) return this.evalDownload.message
        return '下载 Rerank 模型中…'
      }
      if (this.evalProgressTotal > 0) {
        const pct = Math.round(this.evalProgress / this.evalProgressTotal * 100)
        const strategy = this.evalCurrentStrategy ? ` (${this.evalCurrentStrategy})` : ''
        return `回测中 ${pct}%${strategy}`
      }
      return '回测启动中...'
    },
    currentModeDesc() {
      const mode = this.modeOptions.find(m => m.value === this.queryMode)
      return mode?.desc || '上传文档并构建知识库后，您可以提出相关问题'
    },
    heroDescription() {
      if (this.status.vector_store_loaded) {
        return `当前已具备可查询知识库，使用${this.currentModeLabel}继续提问，或切换模型提供者获得不同回答风格。`
      }
      return '适合中文团队的本地优先 Agentic RAG 工作台，支持文档入库、混合检索、多轮对话与智能模式。'
    },
    currentModeLabel() {
      const mode = this.modeOptions.find(m => m.value === this.queryMode)
      return mode?.label || '纯 RAG'
    },
    currentProviderLabel() {
      const opt = this.providerOptions.find(o => o.value === this.provider)
      return opt?.label || '后端默认'
    },
    knowledgeBaseStatus() {
      return this.status.vector_store_loaded ? '已构建，可直接提问' : '未构建，请先上传文档'
    }
  },
  mounted() {
    this.loadSettings()
    loadAuthState()
    this.syncAuthFromStore()
    this.fetchStatus()
    this.handleRouteQuery()
    window.addEventListener('rag-mode-changed', this.onExternalModeChange)
    window.addEventListener('rag-settings-changed', this.loadSettings)

    if (!this.provider) {
      ElMessage.warning('提示：建议在设置中选择 Ollama(本地) 或其他可用的模型提供者')
    }
  },
  beforeUnmount() {
    window.removeEventListener('rag-mode-changed', this.onExternalModeChange)
    window.removeEventListener('rag-settings-changed', this.loadSettings)
    if (this.progressInterval) {
      clearInterval(this.progressInterval)
    }
    // 移除拖拽监听器
    const uploadBox = this.$refs.uploadBox || document.querySelector('.upload-box')
    if (uploadBox) {
      uploadBox.removeEventListener && uploadBox.removeEventListener('dragover', this._dragOverHandler)
      uploadBox.removeEventListener && uploadBox.removeEventListener('dragleave', this._dragLeaveHandler)
      uploadBox.removeEventListener && uploadBox.removeEventListener('drop', this._dropHandler)
    }
  },
  watch: {
    '$route.query'() {
      this.handleRouteQuery()
    },
    kbVisible(val) {
      if (val) {
        // 当抽屉打开时，确保拖拽区域绑定事件
        this.$nextTick(() => this.setupDragDrop())
      } else {
        // 抽屉关闭时移除监听
        const uploadBox = this.$refs.uploadBox || document.querySelector('.upload-box')
        if (uploadBox) {
          uploadBox.removeEventListener && uploadBox.removeEventListener('dragover', this._dragOverHandler)
          uploadBox.removeEventListener && uploadBox.removeEventListener('dragleave', this._dragLeaveHandler)
          uploadBox.removeEventListener && uploadBox.removeEventListener('drop', this._dropHandler)
        }
      }
    }
  },
  methods: {
    authHeaders() { return sharedAuthHeaders() },
    syncAuthFromStore() {
      const auth = useAuthState()
      this.accessToken = auth.accessToken
      this.currentUser = auth.currentUser
    },
    openAuthPanel() {
      this.$router.push({ name: 'login' })
    },
    logout() {
      clearAuthSession()
      this.syncAuthFromStore()
      ElMessage.success('已退出登录')
      this.$router.replace({ name: 'login' })
    },
    async openAdminConsole() {
      this.adminVisible = true
      await this.loadAdminConsole()
    },
    async loadAdminConsole() {
      this.adminLoading = true
      try {
        const headers = this.authHeaders()
        const [summaryRes, auditRes, tenantRes, webhookRes] = await Promise.all([
          axios.get(`${API_BASE}/admin/summary`, { headers }),
          axios.get(`${API_BASE}/admin/audit-events`, { headers }),
          axios.get(`${API_BASE}/admin/tenant-metrics`, { headers }),
          axios.get(`${API_BASE}/admin/webhooks`, { headers })
        ])
        this.adminSummary = summaryRes.data
        this.auditEvents = auditRes.data.events || []
        const tenants = tenantRes.data.tenants || {}
        this.tenantMetrics = Object.entries(tenants).map(([tenant, value]) => ({
          tenant,
          ...value
        }))
        this.webhookStatus = webhookRes.data || { enabled: false, events: [], recent: [] }
      } catch (e) {
        const msg = e.response?.data?.detail || e.message
        ElMessage.error(`加载管理台失败: ${msg}`)
      } finally {
        this.adminLoading = false
      }
    },
    async testWebhook() {
      this.webhookTesting = true
      try {
        const res = await axios.post(`${API_BASE}/admin/webhooks/test`, {}, { headers: this.authHeaders() })
        const ok = res.data?.result?.ok
        ElMessage[ok ? 'success' : 'warning'](ok ? 'Webhook 测试成功' : `Webhook 测试失败: ${res.data?.result?.error || 'unknown'}`)
        await this.loadAdminConsole()
      } catch (e) {
        const msg = e.response?.data?.detail || e.message
        ElMessage.error(`Webhook 测试失败: ${msg}`)
      } finally {
        this.webhookTesting = false
      }
    },
    formatAuditTime(timestamp) {
      if (!timestamp) return ''
      return new Date(timestamp).toLocaleString('zh-CN')
    },
    loadSettings() {
      const saved = localStorage.getItem('ragSettings')
      if (saved) {
        const settings = JSON.parse(saved)
        this.provider = settings.provider || ''
        this.ollamaModel = settings.ollamaModel || ''
        this.ollamaApiUrl = settings.ollamaApiUrl || ''
        this.deepseekModel = settings.deepseekModel || ''
        this.deepseekApiUrl = settings.deepseekApiUrl || ''
        this.deepseekApiKey = settings.deepseekApiKey || ''
        // 加载查询模式（只支持 rag 和 smart）
        if (settings.queryMode === 'rag' || settings.queryMode === 'smart') {
          this.queryMode = settings.queryMode
        } else {
          // 其他旧模式统一转为智能模式
          this.queryMode = 'smart'
        }
      }
    },
    saveSettings() {
      const settings = {
        provider: this.provider,
        ollamaModel: this.ollamaModel,
        ollamaApiUrl: this.ollamaApiUrl,
        deepseekModel: this.deepseekModel,
        deepseekApiUrl: this.deepseekApiUrl,
        deepseekApiKey: this.deepseekApiKey,
        queryMode: this.queryMode
      }
      localStorage.setItem('ragSettings', JSON.stringify(settings))
    },
    loadTheme() {
      try {
        const t = localStorage.getItem('siteTheme') || 'light'
        this.isDark = (t === 'dark')
      } catch (e) {
        this.isDark = false
      }
      this.applyTheme()
    },
    applyTheme() {
      try {
        if (this.isDark) {
          document.documentElement.classList.add('dark')
          localStorage.setItem('siteTheme', 'dark')
        } else {
          document.documentElement.classList.remove('dark')
          localStorage.setItem('siteTheme', 'light')
        }
      } catch (e) {
        // ignore
      }
    },
    toggleTheme() {
      this.isDark = !this.isDark
      this.applyTheme()
      ElMessage.success(this.isDark ? '已切换到深色模式' : '已切换到浅色模式')
    },
    onModeChange(val) {
      this.saveSettings()
      const mode = this.modeOptions.find(m => m.value === val)
      ElMessage.success(`已切换到${mode?.label || val}模式`)
    },
    selectMode(value) {
      this.queryMode = value
      this.modeDropdownOpen = false
      this.onModeChange(value)
    },
    selectProvider(value) {
      this.provider = value
      this.providerDropdownOpen = false
      this.saveSettings()
    },
    async fetchStatus() {
      try {
        const res = await axios.get(`${API_BASE}/status`)
        this.status = res.data
      } catch (e) {
        console.error(e)
      }
    },
    setupDragDrop() {
      const uploadBox = this.$refs.uploadBox || document.querySelector('.upload-box')
      if (!uploadBox) return

      // 为避免重复绑定，先移除可能存在的监听器（简单做法）
      uploadBox.removeEventListener && uploadBox.removeEventListener('dragover', this._dragOverHandler)

      this._dragOverHandler = (e) => {
        e.preventDefault()
        uploadBox.classList.add('dragover')
      }

      this._dragLeaveHandler = () => uploadBox.classList.remove('dragover')

      this._dropHandler = async (e) => {
        e.preventDefault()
        uploadBox.classList.remove('dragover')
        const files = e.dataTransfer.files
        for (let file of files) {
          await this.uploadFile(file)
        }
      }

      uploadBox.addEventListener('dragover', this._dragOverHandler)
      uploadBox.addEventListener('dragleave', this._dragLeaveHandler)
      uploadBox.addEventListener('drop', this._dropHandler)
    },
    triggerFileInput() {
      this.$refs.fileInput.click()
    },
    triggerImageInput() {
      this.$refs.imageInput.click()
    },
    triggerChatFileInput() {
      this.$refs.fileInput2.click()
    },
    applyStarterPrompt(prompt) {
      this.question = prompt
      this.$nextTick(() => {
        const input = this.$refs.chatInput?.textarea || this.$refs.chatInput?.$el?.querySelector('textarea')
        if (input && typeof input.focus === 'function') {
          input.focus()
        }
      })
    },
    async handleFileAttach(e) {
      const files = e.target.files
      if (files && files.length > 0) {
        let addedCount = 0
        for (let file of files) {
          // 限制文件大小（10MB）
          if (file.size > 10 * 1024 * 1024) {
            ElMessage.warning(`文件 ${file.name} 超过10MB，已跳过`)
            continue
          }
          
          try {
            // 读取文件内容
            const content = await this.readFileContent(file)
            this.attachedFiles.push({
              name: file.name,
              type: file.type || this.getFileTypeFromName(file.name),
              size: file.size,
              content: content
            })
            addedCount++
          } catch (err) {
            console.error('文件读取失败:', file.name, err)
            ElMessage.error(`文件 ${file.name} 读取失败`)
          }
        }
        if (addedCount > 0) {
          ElMessage.success(`已添加 ${addedCount} 个文件`)
        }
      }
      // 清空input，允许重复上传同一个文件
      if (this.$refs.fileInput2) {
        this.$refs.fileInput2.value = ''
      }
    },
    async readFileContent(file) {
      return new Promise((resolve, reject) => {
        // 根据文件类型选择读取方式
        const isTextFile = file.type.startsWith('text/') || 
            file.name.endsWith('.txt') || 
            file.name.endsWith('.md') || 
            file.name.endsWith('.json') ||
            file.name.endsWith('.csv')
        
        if (!isTextFile) {
          // 对于二进制文件（PDF, DOCX等），只保存文件信息，不读取内容
          resolve('[二进制文件: ' + file.name + ']')
          return
        }
        
        const reader = new FileReader()
        reader.onload = (e) => {
          const content = e.target.result
          // 对于文本文件，截取前8000字符以节省token
          if (typeof content === 'string') {
            const truncated = content.substring(0, 8000)
            if (content.length > 8000) {
              resolve(truncated + '\n\n[文件内容已截断，仅保留前8000字符]')
            } else {
              resolve(truncated)
            }
          } else {
            resolve(String(content))
          }
        }
        reader.onerror = () => {
          resolve('[无法读取文件: ' + file.name + ']')
        }
        
        reader.readAsText(file)
      })
    },
    getFileTypeFromName(filename) {
      const ext = filename.split('.').pop().toLowerCase()
      const types = {
        'txt': 'text/plain',
        'md': 'text/markdown',
        'json': 'application/json',
        'csv': 'text/csv',
        'pdf': 'application/pdf',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      }
      return types[ext] || 'application/octet-stream'
    },
    getFileIcon(type) {
      if (!type) return '📎'
      const t = String(type).toLowerCase()
      if (t.includes('pdf') || t === '.pdf') return '📄'
      if (t.includes('word') || t.includes('doc') || t === '.docx') return '📝'
      if (t.includes('excel') || t.includes('sheet') || t === '.xls' || t === '.xlsx') return '📊'
      if (t.includes('text') || t.includes('markdown') || t === '.md' || t === '.txt') return '📃'
      if (t.includes('json') || t === '.json') return '📋'
      if (t.includes('csv') || t === '.csv') return '📈'
      if (t === '.py' || t === '.js' || t === '.ts' || t === '.java' || t === '.cpp' || t === '.go') return '💻'
      if (t === '.html' || t === '.htm' || t === '.xml') return '🌐'
      if (t === '.yaml' || t === '.yml' || t === '.ini' || t === '.conf') return '⚙️'
      return '📎'
    },
    removeFile(index) {
      this.attachedFiles.splice(index, 1)
      ElMessage.success('文件已移除')
    },
    async handleFileSelect(e) {
      const files = e.target.files
      for (let file of files) {
        await this.uploadFile(file)
      }
      this.$refs.fileInput.value = ''
    },
    async uploadFile(file) {
      try {
        const formData = new FormData()
        formData.append('file', file)
        
        const res = await axios.post(`${API_BASE}/upload`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
        
        if (res.data.success) {
          this.uploadedFiles.push({
            name: res.data.filename,
            size: res.data.size
          })
          ElMessage.success(`文件 ${file.name} 上传成功`)
        }
      } catch (e) {
        ElMessage.error(`文件 ${file.name} 上传失败: ${e.message}`)
      }
    },
    formatFileSize(bytes) {
      if (!bytes || bytes === 0) return '0 B'
      if (typeof bytes !== 'number' || isNaN(bytes)) return '-'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1)
      return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
    },
    async startBuild() {
      try {
        const res = await axios.post(`${API_BASE}/build-start`)
        if (res.data.success) {
          ElMessage.success('构建任务已启动')
          this.startProgressPolling()
        }
      } catch (e) {
        ElMessage.error(`启动构建失败: ${e.message}`)
      }
    },
    async startIncrementalBuild() {
      try {
        const res = await axios.post(`${API_BASE}/build-incremental`)
        if (res.data.success) {
          ElMessage.success('增量构建已启动')
          this.startProgressPolling()
        }
      } catch (e) {
        ElMessage.error(`增量构建失败: ${e.message}`)
      }
    },
    async runBacktest() {
      this.evalLoading = true
      this.evalProgress = 0
      this.evalProgressTotal = 0
      this.evalCurrentStrategy = ''
      this.evalPhase = ''
      this.evalDownload = null
      try {
        const rerankOptions = this.evalIncludeRerank ? [false, true] : [false]
        await axios.post(`${API_BASE}/eval/backtest-async`, {
          dataset_path: 'data/demo_dataset/qa_pairs.json',
          methods: ['vector', 'bm25', 'hybrid'],
          rerank_options: rerankOptions,
        })

        const poll = async () => {
          const res = await axios.get(`${API_BASE}/eval/backtest-status`)
          const status = res.data
          this.evalProgress = status.progress || 0
          this.evalProgressTotal = status.total || 0
          this.evalCurrentStrategy = status.current_strategy || ''
          this.evalPhase = status.phase || ''
          this.evalDownload = status.download || null
          if (status.running) {
            await new Promise(r => setTimeout(r, 1000))
            return poll()
          }
          if (status.result?.error) {
            throw new Error(status.result.error)
          }
          this.evalReport = status.result
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
          rerank_options: rerankOptions,
        })

        const poll = async () => {
          const res = await axios.get(`${API_BASE}/eval/enterprise-backtest-status`)
          const status = res.data
          this.evalProgress = status.progress || 0
          this.evalProgressTotal = status.total || 0
          this.evalCurrentStrategy = status.current_strategy || ''
          this.evalPhase = status.phase || ''
          this.evalDownload = status.download || null
          if (status.running) {
            await new Promise(r => setTimeout(r, 1000))
            return poll()
          }
          if (status.result?.error) {
            throw new Error(status.result.error)
          }
          this.enterpriseEvalReport = status.result
        }
        await poll()
        ElMessage.success(this.enterpriseEvalReport?.release_gates?.approved ? '企业回测通过' : '企业回测未通过门禁')
      } catch (e) {
        ElMessage.error(`企业回测失败: ${e.response?.data?.detail || e.message}`)
      } finally {
        this.evalLoading = false
        this.evalDownload = null
      }
    },
    async openTraces() {
      this.traceVisible = true
      await this.loadTraces()
    },
    async loadTraces() {
      try {
        const res = await axios.get(`${API_BASE}/traces`)
        this.traceList = res.data.traces || []
      } catch (e) {
        ElMessage.error('加载追踪失败')
      }
    },
    async loadTraceDetail(traceId) {
      try {
        const res = await axios.get(`${API_BASE}/traces/${traceId}`)
        this.traceDetail = res.data
      } catch (e) {
        ElMessage.error('加载追踪详情失败')
      }
    },
    highlightSource(source) {
      source._highlighted = !source._highlighted
    },
    startProgressPolling() {
      if (this.progressInterval) {
        clearInterval(this.progressInterval)
      }
      
      this.progressInterval = setInterval(async () => {
        try {
          const res = await axios.get(`${API_BASE}/build-progress`)
          this.buildProgress = res.data
          
          if (!res.data.processing) {
            clearInterval(this.progressInterval)
            this.progressInterval = null
            
            if (res.data.status === 'completed') {
              this.buildResult = {
                type: 'success',
                message: `✓ 知识库构建成功！共处理 ${res.data.total} 个文档块`
              }
              await this.fetchStatus()
            } else if (res.data.status === 'error') {
              this.buildResult = {
                type: 'error',
                message: `✗ 构建失败: ${res.data.current_file}`
              }
            }
          }
        } catch (e) {
          console.error('获取进度失败:', e)
        }
      }, 500)
    },
    async handleImageSelect(e) {
      const files = e.target.files
      if (files && files.length > 0) {
        for (let file of files) {
          const reader = new FileReader()
          reader.onload = (event) => {
            this.uploadedImages.push(event.target.result)
          }
          reader.readAsDataURL(file)
        }
        ElMessage.success(`已加载 ${files.length} 张图片`)
      }
      this.$refs.imageInput.value = ''
    },
    removeImage(index) {
      this.uploadedImages.splice(index, 1)
      ElMessage.success('图片已移除')
    },
    handlePaste(e) {
      const items = e.clipboardData?.items
      if (items) {
        let imageCount = 0
        for (let item of items) {
          if (item.type.indexOf('image') !== -1) {
            e.preventDefault()
            const file = item.getAsFile()
            const reader = new FileReader()
            reader.onload = (event) => {
              this.uploadedImages.push(event.target.result)
            }
            reader.readAsDataURL(file)
            imageCount++
          }
        }
        if (imageCount > 0) {
          ElMessage.success(`已从剪贴板加载 ${imageCount} 张图片`)
        }
      }
    },
    handleInputKeydown(e) {
      if (e.key === 'Enter' ) {
        e.preventDefault()
        this.sendQuestion()
      }
    },
    
    // 开始新对话
    startNewConversation() {
      this.conversationId = null
      this.messages = []
      ElMessage.success('已开始新对话')
    },
    
    // 加载对话列表
    async loadConversationList() {
      this.historyLoading = true
      try {
        const res = await axios.get(`${API_BASE}/conversations`, { headers: this.authHeaders() })
        if (res.data.success) {
          this.conversationList = res.data.conversations
        }
      } catch (e) {
        console.error('加载对话列表失败:', e)
        ElMessage.error('加载对话列表失败')
      } finally {
        this.historyLoading = false
      }
    },
    
    // 加载指定对话
    async loadConversation(conversationId) {
      try {
        const res = await axios.get(`${API_BASE}/conversations/${conversationId}`, { headers: this.authHeaders() })
        if (res.data.success) {
          // 设置当前会话ID
          this.conversationId = conversationId
          
          // 将历史消息转换为前端格式
          this.messages = res.data.messages.map(msg => ({
            role: msg.role,
            content: msg.content,
            finished: true,
            sources: []
          }))
          ElMessage.success('已加载历史对话，您可以继续对话')
        }
      } catch (e) {
        console.error('加载对话失败:', e)
        ElMessage.error('加载对话失败')
      }
    },
    
    // 删除对话
    async deleteConversation(conversationId) {
      try {
        await ElMessageBox.confirm('确定要删除这个对话吗？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        
        const res = await axios.delete(`${API_BASE}/conversations/${conversationId}`, { headers: this.authHeaders() })
        if (res.data.success) {
          // 从列表中移除
          this.conversationList = this.conversationList.filter(c => c.id !== conversationId)
          
          // 如果删除的是当前对话，清空当前状态
          if (this.conversationId === conversationId) {
            this.conversationId = null
            this.messages = []
          }
          
          ElMessage.success('对话已删除')
        }
      } catch (e) {
        if (e !== 'cancel') {
          console.error('删除对话失败:', e)
          ElMessage.error('删除对话失败')
        }
      }
    },
    
    // 格式化时间
    formatTime(timestamp) {
      if (!timestamp) return ''
      const date = new Date(timestamp)
      const now = new Date()
      const diff = now - date
      
      // 今天内
      if (diff < 24 * 60 * 60 * 1000 && date.getDate() === now.getDate()) {
        return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      }
      
      // 一周内
      if (diff < 7 * 24 * 60 * 60 * 1000) {
        const days = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
        return days[date.getDay()]
      }
      
      // 其他
      return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
    },
    
    // 创建新会话（调用 API）
    async createNewConversation() {
      try {
        const response = await fetch(`${API_BASE}/agent/conversation/create`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...this.authHeaders() }
        })
        
        if (response.ok) {
          const data = await response.json()
          this.conversationId = data.conversation_id
          console.log('[对话] 创建新会话:', this.conversationId)
        } else {
          console.error('[对话] 创建会话失败:', response.status)
        }
      } catch (e) {
        console.error('[对话] 创建会话异常:', e)
      }
    },
    
    async sendQuestion() {
      if (!this.question.trim() && this.uploadedImages.length === 0 && this.attachedFiles.length === 0) return
      
      const q = this.question.trim()
      
      // 如果有附件，将文件内容附加到问题中
      let fullQuestion = q
      if (this.attachedFiles.length > 0) {
        fullQuestion += '\n\n--- 附件内容 ---\n'
        for (const file of this.attachedFiles) {
          fullQuestion += `\n[${file.name}]:\n${file.content}\n`
        }
      }
      
      // 添加用户消息，包含所有图片和文件
      const userMessage = {
        role: 'user',
        content: q,
        finished: true
      }
      
      // 如果有图片，添加到消息中
      if (this.uploadedImages.length > 0) {
        userMessage.images = [...this.uploadedImages]
      }
      
      // 如果有文件，添加到消息中
      if (this.attachedFiles.length > 0) {
        userMessage.files = this.attachedFiles.map(f => ({ name: f.name, size: f.size, type: f.type }))
      }
      
      this.messages.push(userMessage)
      
      // 保存配置
      this.saveSettings()
      this.question = ''
      const imagesToSend = [...this.uploadedImages]
      const filesToSend = [...this.attachedFiles]
      this.uploadedImages = []  // 清空已上传图片
      this.attachedFiles = []  // 清空已附加文件
      this.messageLoading = true
      
      // 根据模式选择不同的处理方式
      if (this.queryMode === 'rag') {
        await this.sendRagQuery(fullQuestion, imagesToSend)
      } else {
        // 智能模式 - 使用智能意图路由
        await this.sendSmartQuery(fullQuestion, imagesToSend)
      }
    },
    
    // 智能路由查询（流式）
    async sendSmartQuery(q) {
      const msgIdx = this.messages.length
      this.messages.push({
        role: 'assistant',
        content: '🤔 正在思考...',
        sources: [],
        thoughtProcess: [],
        toolsUsed: [],
        images: [],
        finished: false,
        streamingTokens: ''
      })

      // RAF 批量刷新：把 token 更新合并到 ~60fps，避免每 token 触发全量重渲染
      let rafId = null
      const flushNow = () => {
        if (rafId) { cancelAnimationFrame(rafId); rafId = null }
        this.messages[msgIdx] = { ...this.messages[msgIdx] }
      }
      const scheduleFlush = () => {
        if (rafId) return
        rafId = requestAnimationFrame(() => { rafId = null; this.messages[msgIdx] = { ...this.messages[msgIdx] } })
      }

      try {
        const payload = {
          question: q,
          conversation_id: this.conversationId || null
        }

        if (this.provider && this.provider.trim()) {
          payload.provider = this.provider.trim()
        }
        if (this.provider === 'ollama') {
          if (this.ollamaModel && this.ollamaModel.trim()) payload.ollama_model = this.ollamaModel.trim()
          if (this.ollamaApiUrl && this.ollamaApiUrl.trim()) payload.ollama_api_url = this.ollamaApiUrl.trim()
        }
        if (this.provider === 'deepseek') {
          if (this.deepseekModel && this.deepseekModel.trim()) payload.deepseek_model = this.deepseekModel.trim()
          if (this.deepseekApiUrl && this.deepseekApiUrl.trim()) payload.deepseek_api_url = this.deepseekApiUrl.trim()
          if (this.deepseekApiKey && this.deepseekApiKey.trim()) payload.deepseek_api_key = this.deepseekApiKey.trim()
        }

        // 如果还没有会话 ID，先创建一个
        if (!this.conversationId) {
          await this.createNewConversation()
          payload.conversation_id = this.conversationId
        }

        const response = await fetch(`${API_BASE}/agent/smart-query-stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...this.authHeaders() },
          body: JSON.stringify(payload)
        })

        if (!response.ok) {
          const errText = await response.text().catch(() => response.statusText)
          throw new Error(`服务返回 ${response.status}: ${errText.slice(0, 200)}`)
        }
        if (!response.body) {
          throw new Error('浏览器未收到流式响应体')
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let answerContent = ''
        let isStreamingAnswer = false
        let streamDone = false

        while (true) {
          const { done, value } = await reader.read()
          if (done || streamDone) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop()

          for (let line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const data = JSON.parse(line.slice(6))

              if (data.type === 'start') {
                this.messages[msgIdx].content = '🧠 ' + (data.data || '正在分析...')
                flushNow()
              } else if (data.type === 'intent') {
                const intentLabels = {
                  knowledge_base: '📚 知识库查询',
                  web_search: '🌐 联网搜索',
                  direct_answer: '💬 直接回答',
                  conversation: '💭 历史对话',
                  file_operation: '📁 文件操作',
                  multi_step: '🔄 多步骤推理',
                  trending: '🔥 热搜趋势',
                  image_generation: '🎨 AI 生成图片',
                }
                const label = intentLabels[data.data?.intent] || data.data?.intent
                const status = `${label}（置信度 ${((data.data?.confidence || 0) * 100).toFixed(0)}%）`
                this.messages[msgIdx].content = status
                this.messages[msgIdx].thoughtProcess.push({
                  step: 0,
                  thought: status + (data.data?.reasoning ? ` — ${data.data.reasoning}` : '')
                })
                flushNow()
              } else if (data.type === 'action') {
                if (!this.messages[msgIdx].toolsUsed.includes(data.data?.tool)) {
                  this.messages[msgIdx].toolsUsed.push(data.data?.tool)
                }
                this.messages[msgIdx].content = `🔧 正在调用 ${data.data?.tool || '工具'}...`
                flushNow()
              } else if (data.type === 'thinking_start') {
                if (!isStreamingAnswer) {
                  this.messages[msgIdx].content = '💭 正在分析...'
                  flushNow()
                }
              } else if (data.type === 'thinking_end') {
                const thought = data.data || ''
                const thoughtMatch = thought.match(/Thought:\s*(.+?)(?=Action:|Final Answer:|$)/s)
                if (thoughtMatch) {
                  this.messages[msgIdx].thoughtProcess.push({
                    step: data.step,
                    thought: thoughtMatch[1].trim()
                  })
                }
                flushNow()
              } else if (data.type === 'answer_start') {
                isStreamingAnswer = true
                answerContent = ''
                // 等首个正式 token 再收起思考区，避免中间空白
                this.messages[msgIdx]._awaitingTokens = true
                flushNow()
              } else if (data.type === 'answer_token') {
                // token 更新走 RAF，批量合并到 ~60fps
                if (data.data == null || data.data === '') {
                  // skip empty tokens
                } else {
                  answerContent += data.data
                  this.messages[msgIdx]._awaitingTokens = false
                  this.messages[msgIdx].content = answerContent
                  this.messages[msgIdx]._reasoningOpen = false
                  scheduleFlush()
                }
              } else if (data.type === 'answer') {
                const finalText = (typeof data.data === 'string' && data.data.trim())
                  ? data.data
                  : (answerContent || '')
                if (finalText.trim()) {
                  this.messages[msgIdx]._awaitingTokens = false
                  this.messages[msgIdx].content = finalText
                  this.messages[msgIdx]._reasoningOpen = false
                }
                flushNow()
              } else if (data.type === 'image') {
                // AI 生成的图片
                if (!this.messages[msgIdx].images) {
                  this.messages[msgIdx].images = []
                }
                if (data.data && data.data.url) {
                  this.messages[msgIdx].images.push(data.data.url)
                }
                flushNow()
              } else if (data.type === 'video') {
                // AI 生成的视频
                if (!this.messages[msgIdx].videos) {
                  this.messages[msgIdx].videos = []
                }
                if (data.data && data.data.url) {
                  this.messages[msgIdx].videos.push(data.data.url)
                }
                flushNow()
              } else if (data.type === 'done') {
                if (data.data?.tools_used) {
                  this.messages[msgIdx].toolsUsed = [
                    ...new Set([...this.messages[msgIdx].toolsUsed, ...data.data.tools_used])
                  ]
                }
                this.finalizeAssistantMessage(msgIdx)
                flushNow()
                streamDone = true
                break
              } else if (data.type === 'error') {
                this.messages[msgIdx].content = `❌ 智能路由错误: ${data.data}`
                this.messages[msgIdx].finished = true
                this.messages[msgIdx].isError = true
                this.messages[msgIdx]._awaitingTokens = false
                this.messageLoading = false
                flushNow()
                ElMessage.error(`智能路由失败: ${data.data}`)
                streamDone = true
                break
              }
            } catch {
              // 忽略非 JSON / 不完整的 SSE 行
            }
          }
        }
      } catch (e) {
        this.messages[msgIdx].content = `❌ 错误: ${e.message}`
        this.messages[msgIdx].isError = true
        flushNow()
        ElMessage.error(`智能路由请求失败: ${e.message}`)
      } finally {
        this.finalizeAssistantMessage(msgIdx)
        flushNow()
        this.messageLoading = false
      }
    },
    
    // Agent 模式查询
    async sendAgentQuery(q, agentType = 'full') {
      const msgIdx = this.messages.length
      // 初始化 Agent 消息
      this.messages.push({
        role: 'assistant',
        content: '🤔 正在思考...',
        sources: [],
        thoughtProcess: [],
        toolsUsed: [],
        images: [],
        finished: false,
        streamingTokens: ''  // 用于累积流式 token
      })

      // RAF 批量刷新，避免每个 token 触发全量重渲染
      let agentRafId = null
      const agentFlushNow = () => {
        if (agentRafId) { cancelAnimationFrame(agentRafId); agentRafId = null }
        this.messages[msgIdx] = { ...this.messages[msgIdx] }
      }
      const agentScheduleFlush = () => {
        if (agentRafId) return
        agentRafId = requestAnimationFrame(() => { agentRafId = null; this.messages[msgIdx] = { ...this.messages[msgIdx] } })
      }
      
      try {
        // 发送请求参数
        const payload = {
          question: q,
          agent_type: agentType,
          provider: this.provider || undefined,  // 添加 provider
          max_iterations: 10,// 最多迭代 10 次
          enable_reflection: true,// 启用反思
          enable_planning: true,// 启用规划
          conversation_id: this.conversationId || null  // 添加会话 ID
        }
        
        // 如果还没有会话 ID，先创建一个
        if (!this.conversationId) {
          await this.createNewConversation()
          payload.conversation_id = this.conversationId
        }
        
        console.log('[Agent] 发送请求，会话ID:', this.conversationId)
        
        // 使用 Agent 流式响应
        const response = await fetch(`${API_BASE}/agent/query-stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...this.authHeaders() },
          body: JSON.stringify(payload)
        })

        if (!response.ok) {
          const errText = await response.text().catch(() => response.statusText)
          throw new Error(`服务返回 ${response.status}: ${errText.slice(0, 200)}`)
        }
        if (!response.body) {
          throw new Error('浏览器未收到流式响应体')
        }
        
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let currentThinkingContent = ''  // 当前思考内容
        let answerContent = ''  // 累积的最终答案
        let isStreamingAnswer = false  // 是否正在流式输出答案
        let agentStreamDone = false
        
        while (true) {
          const { done, value } = await reader.read()
          if (done || agentStreamDone) break
          
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop()
          
          for (let line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                
                if (data.type === 'start') {
                  this.messages[msgIdx].content = '🤔 正在思考...\n'
                  agentFlushNow()
                } else if (data.type === 'iteration') {
                  // 新的迭代开始 - 不显示迭代信息
                } else if (data.type === 'thinking_start') {
                  // 开始思考，重置当前思考内容
                  currentThinkingContent = ''
                  if (!isStreamingAnswer) {
                    this.messages[msgIdx].content = '💭 正在分析...'
                    agentFlushNow()
                  }
                } else if (data.type === 'thinking_end') {
                  // 思考完成，从 data.data 获取完整的思考内容
                  currentThinkingContent = data.data || ''
                  const thoughtMatch = currentThinkingContent.match(/Thought:\s*(.+?)(?=Action:|Final Answer:|$)/s)
                  if (thoughtMatch) {
                    this.messages[msgIdx].thoughtProcess.push({
                      step: data.step,
                      thought: thoughtMatch[1].trim()
                    })
                  }
                  agentFlushNow()
                } else if (data.type === 'thought') {
                  // 兼容旧格式：添加思考步骤
                  this.messages[msgIdx].thoughtProcess.push({
                    step: data.data.step,
                    thought: data.data.thought
                  })
                  this.messages[msgIdx].content = `💭 步骤 ${data.data.step}: ${data.data.thought.substring(0, 100)}...\n`
                  agentFlushNow()
                } else if (data.type === 'action') {
                  // 更新当前步骤的工具信息
                  const currentStep = this.messages[msgIdx].thoughtProcess.length - 1
                  if (currentStep >= 0) {
                    this.messages[msgIdx].thoughtProcess[currentStep].tool = data.data.tool
                  }
                  if (!this.messages[msgIdx].toolsUsed.includes(data.data.tool)) {
                    this.messages[msgIdx].toolsUsed.push(data.data.tool)
                  }
                  agentFlushNow()
                } else if (data.type === 'observation') {
                  // 更新观察结果
                  const currentStep = this.messages[msgIdx].thoughtProcess.length - 1
                  if (currentStep >= 0) {
                    if (data.data && typeof data.data === 'object' && 'text' in data.data) {
                      this.messages[msgIdx].thoughtProcess[currentStep].observation = data.data.text
                      this.messages[msgIdx].thoughtProcess[currentStep].observationData = data.data.data
                    } else {
                      this.messages[msgIdx].thoughtProcess[currentStep].observation = data.data
                    }
                  }
                  agentFlushNow()
                } else if (data.type === 'answer_start') {
                  // 开始流式输出答案 —— 等首个 token 再收起思考区
                  isStreamingAnswer = true
                  answerContent = ''
                  this.messages[msgIdx]._awaitingTokens = true
                  agentFlushNow()
                } else if (data.type === 'answer_token') {
                  // 流式答案 token —— RAF 批量合并，避免每 token 触发重渲染
                  if (data.data != null && data.data !== '') {
                    answerContent += data.data
                    this.messages[msgIdx]._awaitingTokens = false
                    this.messages[msgIdx].content = answerContent
                    this.messages[msgIdx]._reasoningOpen = false
                    agentScheduleFlush()
                  }
                } else if (data.type === 'reflecting') {
                  if (!isStreamingAnswer) {
                    this.messages[msgIdx].content = `🔍 ${data.data}\n`
                    agentFlushNow()
                  }
                } else if (data.type === 'reflection_result') {
                  // 反思结果
                  this.messages[msgIdx].reflection = data.data
                  agentFlushNow()
                } else if (data.type === 'answer') {
                  const finalText = (typeof data.data === 'string' && data.data.trim())
                    ? data.data
                    : (answerContent || '')
                  if (finalText.trim()) {
                    this.messages[msgIdx]._awaitingTokens = false
                    this.messages[msgIdx].content = finalText
                    this.messages[msgIdx]._reasoningOpen = false
                  }
                  agentFlushNow()
                } else if (data.type === 'image') {
                  // AI 生成的图片
                  if (!this.messages[msgIdx].images) {
                    this.messages[msgIdx].images = []
                  }
                  if (data.data && data.data.url) {
                    this.messages[msgIdx].images.push(data.data.url)
                  }
                  agentFlushNow()
                } else if (data.type === 'meta') {
                  this.messages[msgIdx].toolsUsed = data.data.tools_used || []
                  agentFlushNow()
                } else if (data.type === 'done') {
                  this.finalizeAssistantMessage(msgIdx)
                  agentFlushNow()
                  agentStreamDone = true
                  break
                } else if (data.type === 'error') {
                  this.messages[msgIdx].content = `❌ Agent 错误: ${data.data}`
                  this.messages[msgIdx].finished = true
                  this.messages[msgIdx].isError = true
                  this.messages[msgIdx]._awaitingTokens = false
                  this.messageLoading = false
                  agentFlushNow()
                  ElMessage.error(`Agent 查询失败: ${data.data}`)
                  agentStreamDone = true
                  break
                }
              } catch {
                // 忽略非 JSON / 不完整的 SSE 行
              }
            }
          }
        }
      } catch (e) {
        this.messages[msgIdx].content = `❌ 错误: ${e.message}`
        this.messages[msgIdx].finished = true
        this.messages[msgIdx].isError = true
        agentFlushNow()
        ElMessage.error(`Agent 查询失败: ${e.message}`)
      } finally {
        this.finalizeAssistantMessage(msgIdx)
        agentFlushNow()
        this.messageLoading = false
      }
    },
    
    // 普通 RAG 模式查询
    async sendRagQuery(q) {
      let msgIdx = -1
      try {
        const payload = { question: q }
        if (this.provider && this.provider.trim()) {
          payload.provider = this.provider.trim()
        }
        
        // 添加对话历史 - 即使是null也传递，让后端决定是否创建新会话
        payload.conversation_id = this.conversationId || null
        console.log('[对话] 发送请求，当前conversationId:', this.conversationId)
        
        // 添加历史消息（只发送最近的6条消息，3轮对话）
        // 注意：排除刚刚添加的当前用户消息（最后一条）
        if (this.messages.length > 1) {
          const history = this.messages
            .slice(0, -1)  // 排除最后一条（当前用户消息）
            .filter(m => m.finished && !m.isError)
            .slice(-6)
            .map(m => ({
              role: m.role,
              content: m.content
            }))
          if (history.length > 0) {
            payload.history = history
          }
        }
        
        if (this.provider === 'ollama') {
          if (this.ollamaModel && this.ollamaModel.trim()) {
            payload.ollama_model = this.ollamaModel.trim()
          }
          if (this.ollamaApiUrl && this.ollamaApiUrl.trim()) {
            payload.ollama_api_url = this.ollamaApiUrl.trim()
          }
        }
        if (this.provider === 'deepseek') {
          if (this.deepseekModel && this.deepseekModel.trim()) payload.deepseek_model = this.deepseekModel.trim()
          if (this.deepseekApiUrl && this.deepseekApiUrl.trim()) payload.deepseek_api_url = this.deepseekApiUrl.trim()
          if (this.deepseekApiKey && this.deepseekApiKey.trim()) payload.deepseek_api_key = this.deepseekApiKey.trim()
        }
        
        // 添加助手消息占位符
        msgIdx = this.messages.length
        this.messages.push({
          role: 'assistant',
          content: '🤔 正在思考...',
          sources: [],
          thoughtProcess: [],
          finished: false
        })

        // RAF 批量刷新
        let ragRafId = null
        const ragFlushNow = () => {
          if (ragRafId) { cancelAnimationFrame(ragRafId); ragRafId = null }
          this.messages[msgIdx] = { ...this.messages[msgIdx] }
        }
        const ragScheduleFlush = () => {
          if (ragRafId) return
          ragRafId = requestAnimationFrame(() => { ragRafId = null; this.messages[msgIdx] = { ...this.messages[msgIdx] } })
        }
        
        // 使用流式响应
        const response = await fetch(`${API_BASE}/query-stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...this.authHeaders()
          },
          body: JSON.stringify(payload)
        })

        if (!response.ok) {
          const errText = await response.text().catch(() => response.statusText)
          throw new Error(`服务返回 ${response.status}: ${errText.slice(0, 200)}`)
        }
        if (!response.body) {
          throw new Error('浏览器未收到流式响应体')
        }
        
        // 处理服务端发送事件（SSE）
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let ragStreamDone = false
        
        while (true) {
          const { done, value } = await reader.read()
          if (done || ragStreamDone) break
          
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop()
          
          for (let line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                
                if (data.type === 'content') {
                  // data.data 可能是字符串，也可能是对象（例如 {answer: '...'}）
                  let piece = data.data
                  if (piece && typeof piece === 'object') {
                    if (typeof piece.answer === 'string') {
                      piece = piece.answer
                    } else {
                      // 尝试取第一个字符串字段作为候选
                      const keys = Object.keys(piece)
                      let found = false
                      for (const k of keys) {
                        if (typeof piece[k] === 'string') {
                          piece = piece[k]
                          found = true
                          break
                        }
                      }
                      if (!found) {
                        try {
                          piece = JSON.stringify(piece)
                        } catch (e) {
                          piece = String(piece)
                        }
                      }
                    }
                  }

                  // 首个正式 token 到来时清掉思考占位，避免拼进回答
                  const prev = this.messages[msgIdx].content || ''
                  if (!this.hasRealAnswer({ content: prev })) {
                    this.messages[msgIdx].content = typeof piece === 'string' ? piece : String(piece)
                  } else {
                    this.messages[msgIdx].content += (typeof piece === 'string' ? piece : String(piece))
                  }
                } else if (data.type === 'sources') {
                  // 只在第一次接收时设置源信息，并去重
                  if (this.messages[msgIdx].sources.length === 0) {
                    // 去重：按 source 字段去重
                    const uniqueSources = []
                    const seenSources = new Set()
                    for (const src of data.data) {
                      if (!seenSources.has(src.source)) {
                        seenSources.add(src.source)
                        uniqueSources.push(src)
                      }
                    }
                    this.messages[msgIdx].sources = uniqueSources
                  }
                } else if (data.type === 'conversation_id') {
                  // 保存会话ID
                  if (!this.conversationId) {
                    this.conversationId = data.data
                    console.log('[对话] 创建新会话ID:', this.conversationId)
                  }
                } else if (data.type === 'done') {
                  this.finalizeAssistantMessage(msgIdx)
                  ragStreamDone = true
                } else if (data.type === 'error') {
                  // 错误消息以红色显示，并标记为已完成
                  this.messages[msgIdx].content = `❌ 错误: ${data.data}`
                  this.messages[msgIdx].finished = true
                  this.messages[msgIdx].isError = true
                  this.messageLoading = false
                  ElMessage.error(`查询失败: ${data.data}`)
                  ragStreamDone = true
                }
                
                // 只在接收到重要数据时触发更新
                // content 走 RAF 批量刷新，其他结构性事件立即刷新
                if (data.type === 'content') {
                  ragScheduleFlush()
                } else if (['sources', 'conversation_id', 'done', 'error'].includes(data.type)) {
                  ragFlushNow()
                }
              } catch {
                // 忽略非 JSON / 不完整的 SSE 行
              }
            }
          }
        }

        this.finalizeAssistantMessage(msgIdx)
        ragFlushNow()
        
      } catch (e) {
        const err = e.response?.data?.detail || e.message
        if (msgIdx >= 0 && this.messages[msgIdx]) {
          this.messages[msgIdx].content = `❌ 错误: ${err}`
          this.messages[msgIdx].isError = true
          this.finalizeAssistantMessage(msgIdx)
        } else {
          this.messages.push({
            role: 'assistant',
            content: `❌ 错误: ${err}`,
            finished: true,
            isError: true
          })
        }
        ElMessage.error(`查询失败: ${err}`)
      } finally {
        this.messageLoading = false
      }
    },
    isReasoningOpen(msg) {
      if (typeof msg._reasoningOpen === 'boolean') return msg._reasoningOpen
      // 思考中默认展开，回答开始/结束后默认收起
      return this.isMessageThinking(msg)
    },
    toggleReasoning(idx) {
      const msg = this.messages[idx]
      if (!msg) return
      msg._reasoningOpen = !this.isReasoningOpen(msg)
      this.messages[idx] = { ...msg }
    },
    isMessageThinking(msg) {
      if (!msg || msg.role !== 'assistant' || msg.isError) return false
      return !msg.finished && !this.hasRealAnswer(msg)
    },
    thinkingStatusText(msg) {
      const c = (msg?.content || '').trim()
      if (c && !this.hasRealAnswer(msg)) return c
      return '正在思考…'
    },
    finalizeAssistantMessage(msgIdx) {
      const msg = this.messages[msgIdx]
      if (!msg || msg.role !== 'assistant') return
      msg._awaitingTokens = false
      const hasMedia = !!(msg.images?.length || msg.image || msg.videos?.length)
      if (!msg.isError && !hasMedia && !this.hasRealAnswer(msg)) {
        msg.content = '未返回有效内容，请重试。'
        msg.isError = true
      }
      msg.finished = true
      // 有正式回答或错误时收起推理；避免先 finished 再写 content 造成空白帧
      if (this.hasRealAnswer(msg) || msg.isError) {
        msg._reasoningOpen = false
      }
      this.messageLoading = false
      this.messages[msgIdx] = { ...msg }
    },
    hasRealAnswer(msg) {
      const c = (msg?.content || '').trim()
      if (!c) return false
      // 流式过程中的状态占位不算正式回答
      return !/^(🧠|💭|📚|🌐|💬|🔥|🎨|📁|🔄|🤔|🔍|🔧)/.test(c)
    },
    showReasoningBlock(msg) {
      if (msg.thoughtProcess?.length > 0) return true
      // 思考刚开始（含 content 仍为空）也显示，避免只剩头像的空白气泡
      return this.isMessageThinking(msg)
    },
    shouldShowAnswerContent(msg) {
      if (msg.role !== 'assistant') return true
      if (msg.isError) return true
      if (msg.images?.length || msg.image || msg.videos?.length || msg.files?.length) return true
      // 思考中由推理块展示，避免状态文案和指示器重复
      if (this.isMessageThinking(msg)) return false
      const c = (msg.content || '').trim()
      return !!c
    },
    reasoningLabel(msg) {
      if (this.isMessageThinking(msg)) return '正在思考'
      return '已深度思考'
    },
    formatContent(raw) {
      if (!raw || typeof raw !== 'string') return raw

      const stripToolSource = (text) => {
        if (!text || typeof text !== 'string') return text
        return text
          .replace(/\n*\s*来源[:：]\s*工具返回[^\n]*/g, '')
          .replace(/\n{3,}/g, '\n\n')
          .trimEnd()
      }

      const trimmed = raw.trim()

      const tryParse = (str) => {
        try {
          const parsed = JSON.parse(str)
          if (parsed && typeof parsed === 'object') {
            if (typeof parsed.answer === 'string' && parsed.answer.trim().length > 0) return stripToolSource(parsed.answer)
            for (const key of Object.keys(parsed)) {
              const v = parsed[key]
              if (typeof v === 'string' && v.trim().length > 0) return stripToolSource(v)
            }
            return JSON.stringify(parsed)
          }
          if (typeof parsed === 'string') return stripToolSource(parsed)
          return String(parsed)
        } catch (e) {
          return null
        }
      }

      // 1) 直接尝试解析为 JSON
      let out = tryParse(trimmed)
      if (out !== null) return out

      // 2) 如果外层被引号包裹，去掉引号后再尝试解析或返回内部内容
      if ((trimmed.startsWith('"') && trimmed.endsWith('"')) || (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
        const inner = trimmed.slice(1, -1)
        out = tryParse(inner)
        if (out !== null) return out

        // 尝试去掉常见的转义再解析
        try {
          const unescaped = inner.replace(/\\"/g, '"').replace(/\\\\/g, '\\')
          out = tryParse(unescaped)
          if (out !== null) return out
        } catch (e) {
          // ignore
        }

        return stripToolSource(inner)
      }

      // 3) 如果文本中包含 JSON 子串，尝试提取并解析第一个花括号块
      const jsonMatch = trimmed.match(/\{[\s\S]*\}/)
      if (jsonMatch) {
        out = tryParse(jsonMatch[0])
        if (out !== null) return out
      }

      // 否则按原样返回（去掉工具来源标注）
      return stripToolSource(raw)
    },
    
    // 格式化工具返回的 observation，高亮显示 URL 链接和文件名
    formatObservation(obs) {
      if (!obs) return ''
      
      // 限制显示长度
      let text = obs.length > 800 ? obs.substring(0, 800) + '...' : obs
      
      // 转义 HTML 特殊字符
      text = text.replace(/&/g, '&amp;')
                 .replace(/</g, '&lt;')
                 .replace(/>/g, '&gt;')
      
      // 高亮显示 URL（http/https 链接）
      text = text.replace(
        /(https?:\/\/[^\s<>"']+)/g,
        '<a href="$1" target="_blank" class="observation-url">🔗 $1</a>'
      )
      
      // 高亮显示文件路径（以 .md, .txt, .pdf, .docx 等结尾）
      text = text.replace(
        /([^\s<>"']+\.(md|txt|pdf|docx|doc))/gi,
        '<span class="observation-file">📄 $1</span>'
      )
      
      // 高亮显示"来源:"后面的内容
      text = text.replace(
        /(来源[:：]\s*)([^\n]+)/g,
        '$1<span class="observation-source">$2</span>'
      )
      
      return text
    },
    
    onExternalModeChange(e) {
      if (e?.detail === 'rag' || e?.detail === 'smart') {
        this.queryMode = e.detail
      }
    },
    handleRouteQuery() {
      const q = this.$route.query
      if (q.new === '1') {
        this.conversationId = null
        this.messages = []
        this.$router.replace({ name: 'chat', query: {} })
        return
      }
      if (q.c) {
        this.loadConversation(String(q.c))
        this.$router.replace({ name: 'chat', query: {} })
      }
    },

    // ========== 文件管理方法 ==========
    switchToFilesTab() {
      this.kbTab = 'files'
      this.loadFileList()
    },
    async loadFileList() {
      this.fileListLoading = true
      try {
        const res = await axios.get(`${API_BASE}/files`)
        if (res.data.success) {
          this.fileList = res.data.files
        }
      } catch (e) {
        ElMessage.error('加载文件列表失败')
      } finally {
        this.fileListLoading = false
      }
    },
    async openFile(filename) {
      try {
        const res = await axios.get(`${API_BASE}/files/${encodeURIComponent(filename)}`)
        if (res.data.success) {
          this.editingFile = {
            name: res.data.name,
            content: res.data.content,
            originalContent: res.data.content
          }
          this.fileSaveMsg = null
        }
      } catch (e) {
        const msg = e.response?.data?.detail || e.message
        ElMessage.error(`打开文件失败: ${msg}`)
      }
    },
    async saveFile() {
      if (!this.editingFile) return
      this.fileSaving = true
      this.fileSaveMsg = null
      try {
        const res = await axios.put(
          `${API_BASE}/files/${encodeURIComponent(this.editingFile.name)}`,
          { content: this.editingFile.content }
        )
        if (res.data.success) {
          this.editingFile.originalContent = this.editingFile.content
          this.fileSaveMsg = { type: 'success', text: '✅ 已保存' }
          this.loadFileList()
          setTimeout(() => { this.fileSaveMsg = null }, 2000)
        }
      } catch (e) {
        const msg = e.response?.data?.detail || e.message
        this.fileSaveMsg = { type: 'error', text: `❌ 保存失败: ${msg}` }
      } finally {
        this.fileSaving = false
      }
    },
    closeEditor() {
      if (this.editingFile && this.editingFile.content !== this.editingFile.originalContent) {
        if (!confirm('文件有未保存的修改，确定关闭？')) return
      }
      this.editingFile = null
      this.fileSaveMsg = null
    },
    showCreateFile() {
      this.newFileVisible = true
      this.newFileName = ''
    },
    async createNewFile() {
      const name = this.newFileName.trim()
      if (!name) {
        ElMessage.warning('请输入文件名')
        return
      }
      try {
        const res = await axios.post(`${API_BASE}/files`, { name, content: '' })
        if (res.data.success) {
          ElMessage.success('文件已创建')
          this.newFileVisible = false
          await this.loadFileList()
          this.openFile(res.data.name)
        }
      } catch (e) {
        const msg = e.response?.data?.detail || e.message
        ElMessage.error(`创建失败: ${msg}`)
      }
    },
    async confirmDeleteFile(filename) {
      try {
        await ElMessageBox.confirm(`确定要删除文件 "${filename}" 吗？此操作不可恢复。`, '删除确认', {
          confirmButtonText: '删除',
          cancelButtonText: '取消',
          type: 'warning'
        })
        const res = await axios.delete(`${API_BASE}/files/${encodeURIComponent(filename)}`)
        if (res.data.success) {
          ElMessage.success('文件已删除')
          if (this.editingFile && this.editingFile.name === filename) {
            this.editingFile = null
          }
          this.loadFileList()
        }
      } catch (e) {
        if (e !== 'cancel') {
          const msg = e.response?.data?.detail || e.message
          ElMessage.error(`删除失败: ${msg}`)
        }
      }
    }
  }
}
</script>

<style scoped lang="scss">
/* styles loaded globally */

/* 简单的可访问加载转圈指示器 */
.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  margin-left: 8px;
  vertical-align: middle;
  border: 2px solid rgba(0,0,0,0.15);
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 深色模式兼容（如果父级有 .dark 类） */
.dark .spinner {
  border: 2px solid rgba(255,255,255,0.15);
  border-top-color: #67c23a;
}

/* 深色模式增强样式 */
.dark .app-container {
  background: linear-gradient(180deg, #071018 0%, #05070a 100%);
  color: #dbe9f8;
}

.dark .app-header {
  background: linear-gradient(180deg, #081022, #06121a);
  box-shadow: 0 6px 18px rgba(3,8,14,0.6);
  border-bottom: 1px solid rgba(255,255,255,0.03);
}

.dark .header-content .logo-text h1,
.dark .header-content .logo-text p {
  color: #e8f3ff;
}

.dark .main-container {
  background: transparent;
}

.dark .chat-area {
  background: linear-gradient(180deg, rgba(8,12,16,0.6), rgba(5,8,11,0.8));
  border-top: 1px solid rgba(255,255,255,0.02);
}

.dark .empty-state h2,
.dark .empty-state p {
  color: #bfcfe0;
}

.dark .messages-container {
  color: #d6e6f7;
}

.dark .message .message-content {
  background: rgba(255,255,255,0.02);
  color: #dbe9f8;
  border: 1px solid rgba(255,255,255,0.03);
  box-shadow: 0 4px 14px rgba(2,6,10,0.5) inset;
}

.dark .message.user .message-content {
  background: linear-gradient(180deg, rgba(64,158,255,0.10), rgba(64,158,255,0.06));
  color: #e8f6ff;
  border: 1px solid rgba(64,158,255,0.22);
}

.dark .message.assistant .message-content {
  background: rgba(255,255,255,0.02);
  color: #dbe9f8;
}

.dark .message-avatar { opacity: 0.9 }

.dark .input-container {
  background: linear-gradient(180deg, rgba(15, 15, 30, 0.9), rgba(10, 10, 25, 0.95));
  border-top: 1px solid rgba(129, 140, 248, 0.1);
  backdrop-filter: blur(20px);
}

.dark .input-box .chat-input,
.dark .input-box .el-textarea {
  background: transparent !important;
  border: none !important;
}

.dark .input-box .chat-input .el-textarea__inner {
  background: rgba(26, 26, 50, 0.8) !important;
  color: #e8f3ff !important;
  border: 2px solid rgba(129, 140, 248, 0.2) !important;
  border-radius: 12px !important;
}

.dark .input-box .chat-input .el-textarea__inner:focus {
  border-color: var(--primary) !important;
  box-shadow: 0 0 0 3px rgba(129, 140, 248, 0.25) !important;
}

.dark .send-btn {
  background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
  color: #fff !important;
  box-shadow: 0 4px 20px rgba(99, 102, 241, 0.4) !important;
  border-radius: 12px !important;
  border: none !important;
}

.dark .send-btn:hover {
  box-shadow: 0 6px 30px rgba(99, 102, 241, 0.5) !important;
  transform: translateY(-2px);
}

.dark .el-drawer__body {
  background: transparent;
  color: #e2e8f0;
}

.dark .upload-box {
  background: linear-gradient(180deg, rgba(255,255,255,0.01), rgba(255,255,255,0.00));
  border: 1px dashed rgba(255,255,255,0.04);
  color: #cbd7e6;
}

.dark .upload-box.dragover {
  border-color: #67c23a;
  box-shadow: 0 8px 40px rgba(103,194,58,0.06);
}

.dark .build-result.success { color: #67c23a }
.dark .build-result.error { color: #f56c6c }

.dark .message-sources .source-item {
  background: rgba(255,255,255,0.01);
  border: 1px solid rgba(255,255,255,0.02);
  color: #d8e9fb;
}

.dark .observation-url { color: #9fd1ff }
.dark .observation-file { color: #b8d8ff }

.source-item { cursor: pointer; transition: background 0.2s; }
.source-page, .source-chunk { font-size: 11px; color: #409eff; margin-left: 6px; padding: 1px 5px; background: #ecf5ff; border-radius: 3px; }
.source-highlight { margin-top: 6px; padding: 8px; background: #fffbe6; border-left: 3px solid #e6a23c; font-size: 12px; line-height: 1.5; white-space: pre-wrap; }
.eval-panel, .trace-panel { padding: 16px; }
.eval-desc { color: #909399; margin-bottom: 16px; font-size: 13px; }
.eval-results { margin-top: 20px; }
.trace-item { padding: 10px; border: 1px solid #ebeef5; border-radius: 6px; margin-bottom: 8px; cursor: pointer; }
.trace-item:hover { background: #f5f7fa; }
.trace-q { font-weight: 500; margin-bottom: 4px; }
.trace-meta { display: flex; gap: 10px; font-size: 12px; color: #909399; align-items: center; }
.trace-detail { margin-top: 16px; border-top: 1px solid #ebeef5; padding-top: 12px; }
.trace-step { margin-bottom: 10px; padding: 8px; background: #fafafa; border-radius: 4px; }
.trace-step-type { font-weight: 600; color: #409eff; margin-right: 8px; text-transform: uppercase; font-size: 11px; }
.trace-step-tool { font-size: 12px; color: #67c23a; }
.trace-step-content { font-size: 12px; margin-top: 4px; color: #606266; white-space: pre-wrap; }

/* 对话历史样式 */
.history-content {
  padding: 16px;
}

.history-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px;
  color: #909399;
}

.history-empty {
  text-align: center;
  padding: 60px 20px;
  color: #909399;
}

.history-empty .empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.conversation-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.conversation-item {
  padding: 16px;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(255,255,255,0.6), rgba(245,247,250,0.8));
  border: 1px solid rgba(0,0,0,0.06);
  cursor: pointer;
  transition: all 0.2s ease;
}

.conversation-item:hover {
  background: linear-gradient(180deg, rgba(64,158,255,0.08), rgba(64,158,255,0.04));
  border-color: rgba(64,158,255,0.2);
  transform: translateY(-1px);
}

.conversation-item.active {
  background: linear-gradient(180deg, rgba(64,158,255,0.12), rgba(64,158,255,0.06));
  border-color: rgba(64,158,255,0.3);
}

.conv-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.conv-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  line-height: 1.4;
  flex: 1;
  word-break: break-word;
}

.delete-btn {
  opacity: 0;
  transition: opacity 0.2s;
  padding: 4px 8px !important;
  min-height: auto !important;
}

.conversation-item:hover .delete-btn {
  opacity: 1;
}

.conv-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #909399;
}

.conv-count {
  background: rgba(64,158,255,0.1);
  padding: 2px 8px;
  border-radius: 10px;
  color: #409eff;
}

/* 深色模式对话历史 */
.dark .conversation-item {
  background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
  border: 1px solid rgba(255,255,255,0.04);
}

.dark .conversation-item:hover {
  background: linear-gradient(180deg, rgba(64,158,255,0.12), rgba(64,158,255,0.06));
  border-color: rgba(64,158,255,0.25);
}

.dark .conversation-item.active {
  background: linear-gradient(180deg, rgba(64,158,255,0.18), rgba(64,158,255,0.10));
  border-color: rgba(64,158,255,0.35);
}

.dark .conv-title {
  color: #e8f3ff;
}

.dark .conv-meta {
  color: #8a9bb0;
}

.dark .conv-count {
  background: rgba(64,158,255,0.15);
  color: #7db8ff;
}

.dark .history-loading,
.dark .history-empty {
  color: #8a9bb0;
}

::v-deep .el-input__inner {
  border-radius: 0px !important;
}

::v-deep .el-input__wrapper {
  padding: 0px !important;
}

/* ========== 文件管理样式 ========== */
.kb-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 16px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.kb-tab {
  flex: 1;
  padding: 10px 0;
  text-align: center;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  background: rgba(0, 0, 0, 0.02);
  color: #606266;
  user-select: none;
}

.kb-tab.active {
  background: linear-gradient(135deg, #409eff, #66b1ff);
  color: #fff;
  font-weight: 500;
}

.kb-tab:not(.active):hover {
  background: rgba(64, 158, 255, 0.08);
}

.files-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.new-file-form {
  padding: 12px;
  margin-bottom: 12px;
  border-radius: 8px;
  background: rgba(64, 158, 255, 0.04);
  border: 1px solid rgba(64, 158, 255, 0.15);
}

.new-file-form .mb-2 {
  margin-bottom: 8px;
}

.files-loading,
.files-empty {
  text-align: center;
  padding: 30px 16px;
  color: #909399;
}

.file-manager-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 260px;
  overflow-y: auto;
}

.fm-file-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  border: 1px solid transparent;
}

.fm-file-item:hover {
  background: rgba(64, 158, 255, 0.06);
  border-color: rgba(64, 158, 255, 0.12);
}

.fm-file-item.active {
  background: rgba(64, 158, 255, 0.1);
  border-color: rgba(64, 158, 255, 0.25);
}

.fm-file-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.fm-file-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.fm-file-name {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fm-file-meta {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

.fm-delete-btn {
  opacity: 0;
  transition: opacity 0.2s;
  padding: 4px 6px !important;
  min-height: auto !important;
}

.fm-file-item:hover .fm-delete-btn {
  opacity: 1;
}

.file-editor-section {
  margin-top: 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  padding-top: 16px;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.editor-header .section-title {
  margin: 0;
  font-size: 14px;
}

.editor-actions {
  display: flex;
  gap: 6px;
}

.file-editor-textarea .el-textarea__inner {
  font-family: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace !important;
  font-size: 13px !important;
  line-height: 1.6 !important;
  resize: vertical !important;
}

.file-save-msg {
  margin-top: 8px;
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
}

.file-save-msg.success {
  color: #67c23a;
}

.file-save-msg.error {
  color: #f56c6c;
}

/* 深色模式文件管理 */
.dark .kb-tabs {
  border-color: rgba(255, 255, 255, 0.06);
}

.dark .kb-tab {
  background: rgba(255, 255, 255, 0.02);
  color: #a0aec0;
}

.dark .kb-tab.active {
  background: linear-gradient(135deg, #4a7cf7, #6366f1);
  color: #fff;
}

.dark .kb-tab:not(.active):hover {
  background: rgba(255, 255, 255, 0.05);
}

.dark .new-file-form {
  background: rgba(255, 255, 255, 0.02);
  border-color: rgba(255, 255, 255, 0.06);
}

.dark .fm-file-item:hover {
  background: rgba(64, 158, 255, 0.08);
  border-color: rgba(64, 158, 255, 0.15);
}

.dark .fm-file-item.active {
  background: rgba(64, 158, 255, 0.12);
  border-color: rgba(64, 158, 255, 0.25);
}

.dark .fm-file-name {
  color: #e2e8f0;
}

.dark .fm-file-meta {
  color: #718096;
}

.dark .file-editor-section {
  border-top-color: rgba(255, 255, 255, 0.04);
}

.dark .file-editor-textarea .el-textarea__inner {
  background: rgba(15, 15, 30, 0.8) !important;
  color: #e8f3ff !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
}

.settings-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.settings-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 20px 22px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.92));
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
}

.settings-eyebrow {
  margin: 0 0 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #64748b;
}

.settings-heading {
  margin: 0;
  font-size: 20px;
  line-height: 1.3;
  font-weight: 700;
  color: #0f172a;
}

.settings-summary {
  margin: 10px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: #475569;
  max-width: 540px;
}

.settings-status-card {
  min-width: 148px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid rgba(59, 130, 246, 0.12);
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.95), rgba(248, 250, 252, 0.95));
}

.settings-status-label {
  display: block;
  margin-bottom: 6px;
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
}

.settings-status-value {
  display: block;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.settings-group {
  padding: 22px;
  border-radius: 16px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
}

.settings-group::before {
  display: none;
}

.settings-group-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}

.settings-group-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.settings-group-desc {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: #64748b;
}

.settings-field + .settings-field {
  margin-top: 18px;
}

.settings-field-hint {
  margin: 6px 0 10px;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}

.settings-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 18px;
}

.settings-form-grid .settings-field {
  display: flex;
  flex-direction: column;
}

.settings-form-grid .settings-field + .settings-field {
  margin-top: 0;
}

.settings-form-grid .settings-field-hint {
  min-height: 38px;
}

.settings-provider-select .custom-select__trigger {
  min-height: 44px;
  border-radius: 12px;
  border: 1px solid #cbd5e1;
  background: #fff;
}

.settings-provider-select .custom-select__dropdown {
  border-radius: 12px;
}

.settings-note {
  margin-top: 4px;
}

.dark .settings-hero {
  border-color: rgba(129, 140, 248, 0.14);
  background: linear-gradient(180deg, rgba(22, 28, 45, 0.96), rgba(17, 24, 39, 0.96));
  box-shadow: 0 16px 36px rgba(2, 6, 23, 0.45);
}

.dark .settings-eyebrow,
.dark .settings-group-desc,
.dark .settings-field-hint,
.dark .settings-status-label {
  color: #94a3b8;
}

.dark .settings-heading,
.dark .settings-group-title,
.dark .settings-status-value {
  color: #f8fafc;
}

.dark .settings-summary {
  color: #cbd5e1;
}

.dark .settings-status-card {
  border-color: rgba(129, 140, 248, 0.18);
  background: linear-gradient(180deg, rgba(30, 41, 59, 0.92), rgba(15, 23, 42, 0.92));
}

.dark .settings-group {
  border-color: rgba(129, 140, 248, 0.14);
  background: rgba(15, 23, 42, 0.88);
  box-shadow: 0 12px 30px rgba(2, 6, 23, 0.35);
}

.dark .settings-provider-select .custom-select__trigger {
  border-color: rgba(129, 140, 248, 0.22);
  background: rgba(15, 23, 42, 0.72);
}

.admin-panel {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.admin-card {
  padding: 16px;
  border-radius: 14px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.92));
}

.admin-card h3 {
  margin: 0 0 12px;
  font-size: 15px;
  color: #0f172a;
}

.admin-muted {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

.admin-strong {
  margin: 0;
  color: #0f172a;
  font-weight: 600;
}

.admin-kv {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
  font-size: 13px;
}

.admin-kv:last-child {
  border-bottom: none;
}

.admin-subtitle {
  margin: 14px 0 8px;
  font-size: 12px;
  color: #64748b;
}

.admin-tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.admin-tag {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(64, 158, 255, 0.08);
  color: #2563eb;
  font-size: 12px;
}

.audit-item {
  padding: 10px 0;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
}

.audit-item:first-of-type {
  border-top: none;
}

.audit-item__top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
}

.audit-item__meta {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
}

.tenant-metrics-table {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tenant-row {
  display: grid;
  grid-template-columns: 1.4fr 0.8fr 0.9fr 0.9fr 0.9fr;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.03);
  font-size: 12px;
}

.tenant-row--head {
  background: rgba(64, 158, 255, 0.08);
  color: #1d4ed8;
  font-weight: 700;
}

.mb-2 {
  margin-bottom: 8px;
}

.dark .admin-card {
  border-color: rgba(129, 140, 248, 0.14);
  background: rgba(15, 23, 42, 0.88);
}

.dark .admin-card h3,
.dark .admin-strong,
.dark .admin-kv {
  color: #f8fafc;
}

.dark .admin-muted,
.dark .admin-subtitle,
.dark .audit-item__meta {
  color: #94a3b8;
}

.dark .admin-kv,
.dark .audit-item {
  border-color: rgba(148, 163, 184, 0.14);
}

.dark .admin-tag {
  background: rgba(64, 158, 255, 0.14);
  color: #93c5fd;
}

.dark .tenant-row {
  background: rgba(148, 163, 184, 0.08);
  color: #e2e8f0;
}

.dark .tenant-row--head {
  background: rgba(64, 158, 255, 0.18);
  color: #bfdbfe;
}

@media (max-width: 900px) {
  .settings-hero {
    flex-direction: column;
  }

  .settings-status-card {
    width: 100%;
  }

  .settings-form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
