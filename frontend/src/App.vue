<template>
  <div class="app-container">
    <!-- 顶部导航栏 -->
    <header class="app-header">
      <div class="header-content">
        <div class="logo-section">
          <div class="logo-icon floating">✨</div>
          <div class="logo-text">
            <h1 class="gradient-text">Agent 知识库</h1>
            <p>智能知识检索助手</p>
          </div>
        </div>
        <div class="header-stats">
          <div class="stat-item">
            <!-- <span class="stat-label">状态</span> -->
            <!-- <span :class="['stat-value', status.vector_store_loaded ? 'loaded' : 'unloaded']">
              {{ status.vector_store_loaded ? '✓ 已加载' : '✗ 未加载' }}
            </span> -->
          </div>
          <!-- 模式选择 -->
          <div class="custom-select mr-3" :class="{ 'is-open': modeDropdownOpen }" v-click-outside="() => modeDropdownOpen = false">
            <div class="custom-select__trigger" @click="modeDropdownOpen = !modeDropdownOpen">
              <span class="custom-select__value">{{ currentModeLabel }}</span>
              <span class="custom-select__arrow">▾</span>
            </div>
            <div class="custom-select__dropdown" v-show="modeDropdownOpen">
              <div
                v-for="mode in modeOptions"
                :key="mode.value"
                class="custom-select__option"
                :class="{ 'is-selected': queryMode === mode.value }"
                @click="selectMode(mode.value)"
              >
                {{ mode.icon }} {{ mode.label }}
              </div>
            </div>
          </div>
          
          <el-button
            type="primary"
            @click="kbVisible = true"
            class="mr-2 hover-lift"
          >
            📚 知识库
          </el-button>

          <el-button
            type="default"
            @click="historyVisible = true"
            class="mr-2 hover-lift"
            title="查看对话历史"
          >
            📜 历史
          </el-button>

          <el-button
            type="default"
            @click="startNewConversation"
            class="mr-2 hover-lift"
            :title="conversationId ? '开始新对话' : '当前是新对话'"
          >
            ✨ 新对话
          </el-button>

          <el-button
            type="text"
            @click="toggleTheme"
            class="mr-2 theme-toggle-btn"
            :title="isDark ? '切换到浅色模式' : '切换到深色模式'"
          >
            <span v-if="isDark" class="theme-icon">☀️</span>
            <span v-else class="theme-icon">🌙</span>
          </el-button>

          <el-button
            type="primary"
            :icon="Setting"
            @click="settingsVisible = true"
            class="hover-lift"
          >
            ⚙️ 设置
          </el-button>
        </div>
      </div>
    </header>

    <!-- 主容器 -->
    <div class="main-container">
      <!-- 知识库抽屉（包含上传与构建） -->
      <el-drawer v-model="kbVisible" title="📚 知识库管理" size="35%">
        <div class="sidebar-content">
          <div class="sidebar-section">
            <h3 class="section-title">📤 上传文档</h3>
            <div class="upload-area">
              <input
                ref="fileInput"
                type="file"
                multiple
                style="display: none"
                @change="handleFileSelect"
                accept=".md,.pdf,.docx,.txt"
              />
              <div class="upload-box hover-lift" ref="uploadBox" @click="triggerFileInput">
                <div class="upload-icon">📎</div>
                <p>点击选择或拖拽文件</p>
                <span class="upload-hint">支持 MD、PDF、DOCX、TXT</span>
              </div>

              <!-- 已上传文件列表 -->
              <div v-if="uploadedFiles.length > 0" class="uploaded-files">
                <div v-for="(file, idx) in uploadedFiles" :key="idx" class="file-item">
                  <span class="file-name">{{ file.name }}</span>
                  <span class="file-size">{{ formatFileSize(file.size) }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 知识库构建 -->
          <div class="sidebar-section">
            <h3 class="section-title">🏗️ 构建知识库</h3>
            <el-button
              type="primary"
              @click="startBuild"
              :loading="buildProgress.processing"
              class="build-btn"
            >
              {{ buildProgress.processing ? '构建中...' : '开始构建' }}
            </el-button>

            <!-- 构建进度 -->
            <div v-if="buildProgress.processing" class="build-progress">
              <div class="progress-item">
                <span class="progress-label">{{ buildProgress.current_file }}</span>
                <el-progress
                  :percentage="progressPercentage"
                  :color="progressColor"
                />
              </div>
              <p class="progress-info">
                {{ buildProgress.progress }} / {{ buildProgress.total }} 文档块
              </p>
            </div>

            <!-- 构建结果 -->
            <div v-if="buildResult" :class="['build-result', buildResult.type, 'appear']">
              <span v-if="buildResult.type === 'success'">✅</span>
              <span v-else>❌</span>
              {{ buildResult.message }}
            </div>
          </div>
        </div>
      </el-drawer>

      <!-- 主聊天区域 -->
      <main class="chat-area">
        <div class="messages-container">
          <div v-if="messages.length === 0" class="empty-state">
            <div class="empty-icon floating">🚀</div>
            <h2>开始探索知识</h2>
            <p>{{ currentModeDesc }}</p>
            <div class="empty-hints">
              <div class="hint-card glass-card hover-lift">
                <span class="hint-icon">💡</span>
                <span class="hint-text">上传文档构建知识库</span>
              </div>
              <div class="hint-card glass-card hover-lift">
                <span class="hint-icon">🔍</span>
                <span class="hint-text">智能检索精准答案</span>
              </div>
              <div class="hint-card glass-card hover-lift">
                <span class="hint-icon">🤖</span>
                <span class="hint-text">AI 助手随时待命</span>
              </div>
            </div>
          </div>

          <div v-for="(msg, idx) in messages" :key="idx" :class="['message', msg.role, { 'error-message': msg.isError }]">
            <div class="message-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
            <div class="message-content-wrapper">
              <div :class="['message-content', { 'error-content': msg.isError }]">
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
                      <li v-for="(source, sidx) in msg.sources" :key="sidx" class="source-item">
                        <div class="source-title">{{ source.source }}</div>
                        <div class="source-preview">{{ source.preview }}</div>
                      </li>
                    </ul>
                  </el-collapse-item>
                </el-collapse>
              </div>
              
              <!-- Agent 思维过程 -->
              <div v-if="msg.thoughtProcess && msg.thoughtProcess.length > 0" class="message-thoughts">
                <el-collapse>
                  <el-collapse-item title=" Agent 推理过程" name="thoughts">
                    <div class="thought-steps">
                      <div v-for="(step, tidx) in msg.thoughtProcess" :key="tidx" class="thought-step">
                        <div class="step-header">
                          <span class="step-number">步骤 {{ step.step }}</span>
                          <span v-if="step.tool" class="step-tool">🔧 {{ step.tool }}</span>
                        </div>
                        <div class="step-thought">💭 {{ step.thought }}</div>
                        <div v-if="step.observation" class="step-observation">
                          <div class="observation-label">📋 工具返回结果（可核实来源）:</div>
                          <!-- 如果有结构化数据，优先显示列表格式 -->
                          <div v-if="step.observationData && Array.isArray(step.observationData)" class="observation-list">
                            <div v-for="(item, idx) in step.observationData.slice(0, 10)" :key="idx" class="list-item">
                              <div v-if="item.rank" class="item-rank">{{ item.rank }}</div>
                              <div class="item-content">
                                <div v-if="item.title" class="item-title">{{ item.title }}</div>
                                <div v-if="item.url" class="item-url">
                                  <a :href="item.url" target="_blank" class="observation-url">🔗 {{ item.url }}</a>
                                </div>
                                <div v-if="item.hot_value" class="item-hot">热度: {{ item.hot_value }}</div>
                              </div>
                            </div>
                          </div>
                          <!-- 否则显示文本格式 -->
                          <div v-else class="observation-content" v-html="formatObservation(step.observation)"></div>
                        </div>
                      </div>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>
              
              <!-- Agent 使用的工具 -->
              <div v-if="msg.toolsUsed && msg.toolsUsed.length > 0" class="message-tools">
                <span class="tools-label">使用工具:</span>
                <el-tag v-for="tool in msg.toolsUsed" :key="tool" size="small" type="info" class="tool-tag">
                  {{ tool }}
                </el-tag>
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
                <span class="upload-icon">📎</span>
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

    <!-- 对话历史抽屉 -->
    <el-drawer v-model="historyVisible" title="对话历史" size="35%" @open="loadConversationList">
      <div class="history-content">
        <div v-if="historyLoading" class="history-loading">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>加载中...</span>
        </div>
        
        <div v-else-if="conversationList.length === 0" class="history-empty">
          <div class="empty-icon">💬</div>
          <p>暂无对话历史</p>
        </div>
        
        <div v-else class="conversation-list">
          <div 
            v-for="conv in conversationList" 
            :key="conv.id"
            :class="['conversation-item', { active: conv.id === conversationId }]"
            @click="loadConversation(conv.id)"
          >
            <div class="conv-header">
              <span class="conv-title">{{ conv.title }}</span>
              <el-button
                type="text"
                size="small"
                @click.stop="deleteConversation(conv.id)"
                class="delete-btn"
                title="删除对话"
              >
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
    </el-drawer>

    <!-- 设置抽屉 -->
    <el-drawer v-model="settingsVisible" title="模型配置" size="35%">
      <div class="settings-content">
        <div class="settings-group">
          <label class="settings-label">模型提供者</label>
          <div class="custom-select full-width" :class="{ 'is-open': providerDropdownOpen }" v-click-outside="() => providerDropdownOpen = false">
            <div class="custom-select__trigger" @click="providerDropdownOpen = !providerDropdownOpen">
              <span class="custom-select__value">{{ currentProviderLabel }}</span>
              <span class="custom-select__arrow">▾</span>
            </div>
            <div class="custom-select__dropdown"  v-show="providerDropdownOpen">
              <div
                v-for="opt in providerOptions"
                :key="opt.value"
                class="custom-select__option"
                :class="{ 'is-selected': provider === opt.value }"
                @click="selectProvider(opt.value)"
              >
                {{ opt.label }}
              </div>
            </div>
          </div>
        </div>

        <!-- Ollama 配置 -->
        <div v-if="provider === 'ollama'" class="settings-group">
          <label class="settings-label">Ollama 模型</label>
          <el-input
            v-model="ollamaModel"
            placeholder="例如: gemma3:4b"
            clearable
          />

          <label class="settings-label mt-4">Ollama API URL</label>
          <el-input
            v-model="ollamaApiUrl"
            placeholder="例如: http://localhost:11434"
            clearable
          />
        </div>

        <!-- DeepSeek 配置 -->
        <div v-if="provider === 'deepseek'" class="settings-group">
          <label class="settings-label">DeepSeek 模型</label>
          <el-input v-model="deepseekModel" placeholder="例如: deepseek-v1" clearable />

          <div style="display:flex;gap:8px;margin-top:12px;">
            <div style="flex:1;">
              <label class="settings-label">API URL</label>
              <el-input v-model="deepseekApiUrl" placeholder="例如: https://api.deepseek.ai" clearable />
            </div>
            <div style="flex:1;">
              <label class="settings-label">API Key</label>
              <el-input v-model="deepseekApiKey" placeholder="DeepSeek API Key" show-password clearable />
            </div>
          </div>
        </div>

        <div class="settings-info">
          <el-alert
            title="提示"
            type="info"
            :closable="false"
            description="模型配置将实时保存到浏览器本地存储"
          />
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script>
import axios from 'axios'
import { Setting, PictureFilled, Loading } from '@element-plus/icons-vue'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export default {
  components: {
    Setting,
    PictureFilled,
    Loading
  },
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
      // 主题：暗色模式开关
      isDark: false,
      question: '',
      messages: [],
      conversationId: null,  // 当前会话ID
      status: { vector_store_loaded: false },
      settingsVisible: false,
      kbVisible: false,
      historyVisible: false,  // 对话历史抽屉
      messageLoading: false,
      
      // 对话历史
      conversationList: [],
      historyLoading: false,
      
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
      attachedFiles: []
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
    currentModeDesc() {
      const mode = this.modeOptions.find(m => m.value === this.queryMode)
      return mode?.desc || '上传文档并构建知识库后，您可以提出相关问题'
    },
    currentModeLabel() {
      const mode = this.modeOptions.find(m => m.value === this.queryMode)
      return mode?.label || '纯 RAG'
    },
    currentProviderLabel() {
      const opt = this.providerOptions.find(o => o.value === this.provider)
      return opt?.label || '后端默认'
    }
  },
  mounted() {
    // 从 localStorage 加载配置
    this.loadSettings()
    // 加载主题偏好
    this.loadTheme()
    this.fetchStatus()
    
    // 如果没有设置 provider，推荐使用 Ollama
    if (!this.provider) {
      this.$message.warning('提示：建议在设置中选择 Ollama(本地) 或其他可用的模型提供者')
    }
    
    // 支持拖拽上传
    // 延迟到抽屉打开时设置拖拽（也在 mounted 时尝试一次以防抽屉默认打开）
    this.setupDragDrop()
  },
  beforeUnmount() {
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
      this.$message.success(this.isDark ? '已切换到深色模式' : '已切换到浅色模式')
    },
    onModeChange(val) {
      this.saveSettings()
      const mode = this.modeOptions.find(m => m.value === val)
      this.$message.success(`已切换到${mode?.label || val}模式`)
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
    async handleFileAttach(e) {
      const files = e.target.files
      if (files && files.length > 0) {
        let addedCount = 0
        for (let file of files) {
          // 限制文件大小（10MB）
          if (file.size > 10 * 1024 * 1024) {
            this.$message.warning(`文件 ${file.name} 超过10MB，已跳过`)
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
            this.$message.error(`文件 ${file.name} 读取失败`)
          }
        }
        if (addedCount > 0) {
          this.$message.success(`已添加 ${addedCount} 个文件`)
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
      if (t.includes('pdf')) return '📄'
      if (t.includes('word') || t.includes('doc')) return '📝'
      if (t.includes('excel') || t.includes('sheet')) return '📊'
      if (t.includes('text') || t.includes('markdown')) return '📃'
      if (t.includes('json')) return '📋'
      if (t.includes('csv')) return '📈'
      return '📎'
    },
    removeFile(index) {
      this.attachedFiles.splice(index, 1)
      this.$message.success('文件已移除')
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
          this.$message.success(`文件 ${file.name} 上传成功`)
        }
      } catch (e) {
        this.$message.error(`文件 ${file.name} 上传失败: ${e.message}`)
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
          this.$message.success('构建任务已启动')
          this.startProgressPolling()
        }
      } catch (e) {
        this.$message.error(`启动构建失败: ${e.message}`)
      }
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
        this.$message.success(`已加载 ${files.length} 张图片`)
      }
      this.$refs.imageInput.value = ''
    },
    removeImage(index) {
      this.uploadedImages.splice(index, 1)
      this.$message.success('图片已移除')
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
          this.$message.success(`已从剪贴板加载 ${imageCount} 张图片`)
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
      this.$message.success('已开始新对话')
    },
    
    // 加载对话列表
    async loadConversationList() {
      this.historyLoading = true
      try {
        const res = await axios.get(`${API_BASE}/conversations`)
        if (res.data.success) {
          this.conversationList = res.data.conversations
        }
      } catch (e) {
        console.error('加载对话列表失败:', e)
        this.$message.error('加载对话列表失败')
      } finally {
        this.historyLoading = false
      }
    },
    
    // 加载指定对话
    async loadConversation(conversationId) {
      try {
        const res = await axios.get(`${API_BASE}/conversations/${conversationId}`)
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
          
          // 关闭抽屉
          this.historyVisible = false
          
          this.$message.success('已加载历史对话，您可以继续对话')
        }
      } catch (e) {
        console.error('加载对话失败:', e)
        this.$message.error('加载对话失败')
      }
    },
    
    // 删除对话
    async deleteConversation(conversationId) {
      try {
        await this.$confirm('确定要删除这个对话吗？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        
        const res = await axios.delete(`${API_BASE}/conversations/${conversationId}`)
        if (res.data.success) {
          // 从列表中移除
          this.conversationList = this.conversationList.filter(c => c.id !== conversationId)
          
          // 如果删除的是当前对话，清空当前状态
          if (this.conversationId === conversationId) {
            this.conversationId = null
            this.messages = []
          }
          
          this.$message.success('对话已删除')
        }
      } catch (e) {
        if (e !== 'cancel') {
          console.error('删除对话失败:', e)
          this.$message.error('删除对话失败')
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
          headers: { 'Content-Type': 'application/json' }
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
    
    // 智能路由查询
    async sendSmartQuery(q) {
      const msgIdx = this.messages.length
      this.messages.push({
        role: 'assistant',
        content: '',
        sources: [],
        finished: false
      })
      
      try {
        const payload = {
          question: q,
          conversation_id: this.conversationId || null
        }
        
        const response = await fetch(`${API_BASE}/agent/smart-query`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
        
        const data = await response.json()
        if (data.success) {
          this.messages[msgIdx].content = data.answer
          this.messages[msgIdx].sources = data.sources || []
          
          // 如果还没有会话 ID，创建一个
          if (!this.conversationId) {
            await this.createNewConversation()
          }
        } else {
          this.messages[msgIdx].content = data.error || '查询失败'
          this.messages[msgIdx].isError = true
        }
      } catch (e) {
        this.messages[msgIdx].content = `请求失败: ${e.message}`
        this.messages[msgIdx].isError = true
      } finally {
        this.messages[msgIdx].finished = true
        this.messageLoading = false
      }
    },
    
    // Agent 模式查询
    async sendAgentQuery(q, agentType = 'full') {
      const msgIdx = this.messages.length
      // 初始化 Agent 消息
      this.messages.push({
        role: 'assistant',
        content: '',
        sources: [],
        thoughtProcess: [],
        toolsUsed: [],
        finished: false,
        streamingTokens: ''  // 用于累积流式 token
      })
      
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
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
        
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let currentThinkingContent = ''  // 当前思考内容
        let answerContent = ''  // 累积的最终答案
        let isStreamingAnswer = false  // 是否正在流式输出答案
        
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop()
          
          for (let line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                
                if (data.type === 'start') {
                  this.messages[msgIdx].content = '🤔 正在思考...\n'
                } else if (data.type === 'iteration') {
                  // 新的迭代开始 - 不显示迭代信息
                  // if (!isStreamingAnswer) {
                  //   this.messages[msgIdx].content = `🔄 迭代 ${data.data.iteration}/${data.data.max}\n`
                  // }
                } else if (data.type === 'thinking_start') {
                  // 开始思考，重置当前思考内容
                  currentThinkingContent = ''
                  if (!isStreamingAnswer) {
                    this.messages[msgIdx].content = '💭 正在分析...'
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
                } else if (data.type === 'thought') {
                  // 兼容旧格式：添加思考步骤
                  this.messages[msgIdx].thoughtProcess.push({
                    step: data.data.step,
                    thought: data.data.thought
                  })
                  this.messages[msgIdx].content = `💭 步骤 ${data.data.step}: ${data.data.thought.substring(0, 100)}...\n`
                } else if (data.type === 'action') {
                  // 更新当前步骤的工具信息
                  const currentStep = this.messages[msgIdx].thoughtProcess.length - 1
                  if (currentStep >= 0) {
                    this.messages[msgIdx].thoughtProcess[currentStep].tool = data.data.tool
                  }
                  if (!this.messages[msgIdx].toolsUsed.includes(data.data.tool)) {
                    this.messages[msgIdx].toolsUsed.push(data.data.tool)
                  }
                  // 不再显示"使用工具"的中间状态
                  // if (!isStreamingAnswer) {
                  //   this.messages[msgIdx].content = `🔧 使用工具: ${data.data.tool}\n`
                  // }
                } else if (data.type === 'observation') {
                  // 更新观察结果
                  const currentStep = this.messages[msgIdx].thoughtProcess.length - 1
                  if (currentStep >= 0) {
                    // 新格式: data.data 是 {text: '...', data: structured_data}
                    // 旧格式: data.data 是纯文本字符串
                    if (data.data && typeof data.data === 'object' && 'text' in data.data) {
                      this.messages[msgIdx].thoughtProcess[currentStep].observation = data.data.text
                      this.messages[msgIdx].thoughtProcess[currentStep].observationData = data.data.data
                    } else {
                      // 向后兼容：如果是纯字符串，则直接使用
                      this.messages[msgIdx].thoughtProcess[currentStep].observation = data.data
                    }
                  }
                  // 不再显示"获取到工具结果"的中间状态
                  // if (!isStreamingAnswer) {
                  //   this.messages[msgIdx].content = `📋 获取到工具结果...\n`
                  // }
                } else if (data.type === 'answer_start') {
                  // 开始流式输出答案
                  isStreamingAnswer = true
                  answerContent = ''
                  this.messages[msgIdx].content = ''
                } else if (data.type === 'answer_token') {
                  // 流式答案 token
                  answerContent += data.data
                  this.messages[msgIdx].content = answerContent
                } else if (data.type === 'reflecting') {
                  if (!isStreamingAnswer) {
                    this.messages[msgIdx].content = `🔍 ${data.data}\n`
                  }
                } else if (data.type === 'reflection_result') {
                  // 反思结果
                  this.messages[msgIdx].reflection = data.data
                } else if (data.type === 'answer') {
                  this.messages[msgIdx].content = data.data
                } else if (data.type === 'meta') {
                  this.messages[msgIdx].toolsUsed = data.data.tools_used || []
                } else if (data.type === 'done') {
                  this.messages[msgIdx].finished = true
                } else if (data.type === 'error') {
                  this.messages[msgIdx].content = `❌ Agent 错误: ${data.data}`
                  this.messages[msgIdx].finished = true
                  this.messages[msgIdx].isError = true
                  this.$message.error(`Agent 查询失败: ${data.data}`)
                }
                
                this.messages[msgIdx] = { ...this.messages[msgIdx] }
              } catch (parseErr) {
                console.error('解析 Agent SSE 数据失败:', line, parseErr)
              }
            }
          }
        }
      } catch (e) {
        this.messages[msgIdx].content = `❌ 错误: ${e.message}`
        this.messages[msgIdx].finished = true
        this.messages[msgIdx].isError = true
        this.$message.error(`Agent 查询失败: ${e.message}`)
      } finally {
        this.messageLoading = false
      }
    },
    
    // 普通 RAG 模式查询
    async sendRagQuery(q) {
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
        const msgIdx = this.messages.length
        this.messages.push({
          role: 'assistant',
          content: '',
          sources: [],
          finished: false
        })
        
        // 使用流式响应
        const response = await fetch(`${API_BASE}/query-stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(payload)
        })
        
        // 处理服务端发送事件（SSE）
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          
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

                  // 确保追加的是字符串
                  this.messages[msgIdx].content += (typeof piece === 'string' ? piece : String(piece))
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
                  this.messages[msgIdx].finished = true
                } else if (data.type === 'error') {
                  // 错误消息以红色显示，并标记为已完成
                  this.messages[msgIdx].content = `❌ 错误: ${data.data}`
                  this.messages[msgIdx].finished = true
                  this.messages[msgIdx].isError = true
                  this.$message.error(`查询失败: ${data.data}`)
                }
                
                // 只在接收到重要数据时触发更新
                if (['content', 'sources', 'done', 'error'].includes(data.type)) {
                  this.messages[msgIdx] = { ...this.messages[msgIdx] }
                }
              } catch (parseErr) {
                console.error('解析 SSE 数据失败:', line, parseErr)
              }
            }
          }
        }
        
      } catch (e) {
        const err = e.response?.data?.detail || e.message
        this.messages.push({
          role: 'assistant',
          content: `错误: ${err}`,
          finished: true
        })
      } finally {
        this.messageLoading = false
      }
    },
    formatContent(raw) {
      if (!raw || typeof raw !== 'string') return raw

      const trimmed = raw.trim()

      const tryParse = (str) => {
        try {
          const parsed = JSON.parse(str)
          if (parsed && typeof parsed === 'object') {
            if (typeof parsed.answer === 'string' && parsed.answer.trim().length > 0) return parsed.answer
            for (const key of Object.keys(parsed)) {
              const v = parsed[key]
              if (typeof v === 'string' && v.trim().length > 0) return v
            }
            return JSON.stringify(parsed)
          }
          if (typeof parsed === 'string') return parsed
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

        return inner
      }

      // 3) 如果文本中包含 JSON 子串，尝试提取并解析第一个花括号块
      const jsonMatch = trimmed.match(/\{[\s\S]*\}/)
      if (jsonMatch) {
        out = tryParse(jsonMatch[0])
        if (out !== null) return out
      }

      // 否则按原样返回
      return raw
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
    }
  }
}
</script>

<style scoped lang="scss">
@import './styles.css';

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
</style>
