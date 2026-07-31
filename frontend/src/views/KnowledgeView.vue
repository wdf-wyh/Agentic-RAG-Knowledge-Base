<template>
  <div class="page-shell kb-page">
    <div class="page-hero kb-hero">
      <div>
        <p class="page-eyebrow">Knowledge Base</p>
        <h2 class="page-title">知识库管理</h2>
        <p class="page-desc">上传文档、构建索引，并管理知识库源文件。</p>
      </div>
      <div class="kb-hero__aside">
        <div class="kb-status" :class="status.vector_store_loaded ? 'is-ready' : 'is-empty'">
          <span class="kb-status__dot" aria-hidden="true" />
          <div>
            <span class="kb-status__label">向量库状态</span>
            <span class="kb-status__value">{{ status.vector_store_loaded ? '已加载' : '未加载' }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="kb-segment" role="tablist" aria-label="知识库功能">
      <button
        type="button"
        role="tab"
        class="kb-segment__item"
        :class="{ 'is-active': kbTab === 'upload' }"
        :aria-selected="kbTab === 'upload'"
        @click="kbTab = 'upload'"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M12 16V4M12 4l-4 4M12 4l4 4" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" stroke-linecap="round" />
        </svg>
        上传构建
      </button>
      <button
        type="button"
        role="tab"
        class="kb-segment__item"
        :class="{ 'is-active': kbTab === 'files' }"
        :aria-selected="kbTab === 'files'"
        @click="switchToFilesTab"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" stroke-linejoin="round" />
        </svg>
        文件管理
      </button>
    </div>

    <div v-show="kbTab === 'upload'" class="kb-grid" role="tabpanel">
      <section class="kb-panel">
        <div class="kb-panel__head">
          <div>
            <h3>上传文档</h3>
            <p>拖入或选择文件，支持批量上传。</p>
          </div>
        </div>

        <input
          ref="fileInput"
          type="file"
          multiple
          class="kb-file-input"
          accept=".md,.pdf,.docx,.txt"
          @change="handleFileSelect"
        />

        <div
          ref="uploadBox"
          class="kb-dropzone"
          :class="{ 'is-dragover': isDragOver }"
          role="button"
          tabindex="0"
          @click="triggerFileInput"
          @keydown.enter.prevent="triggerFileInput"
          @keydown.space.prevent="triggerFileInput"
        >
          <div class="kb-dropzone__icon" aria-hidden="true">
            <svg viewBox="0 0 48 48" fill="none">
              <rect x="8" y="10" width="32" height="28" rx="6" stroke="currentColor" stroke-width="2" />
              <path d="M24 18v14M24 18l-5 5M24 18l5 5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </div>
          <p class="kb-dropzone__title">点击选择或拖拽文件到此处</p>
          <p class="kb-dropzone__hint">MD · PDF · DOCX · TXT</p>
        </div>

        <div v-if="uploadedFiles.length > 0" class="kb-upload-list">
          <div class="kb-upload-list__head">
            <span>本次已上传</span>
            <span>{{ uploadedFiles.length }} 个文件</span>
          </div>
          <div
            v-for="(file, idx) in uploadedFiles"
            :key="`${file.name}-${idx}`"
            class="kb-upload-item"
          >
            <span class="kb-upload-item__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5z" stroke-linejoin="round" />
                <path d="M14 3v5h5" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </span>
            <span class="kb-upload-item__name">{{ file.name }}</span>
            <span class="kb-upload-item__size">{{ formatFileSize(file.size) }}</span>
          </div>
        </div>
      </section>

      <section class="kb-panel">
        <div class="kb-panel__head">
          <div>
            <h3>构建知识库</h3>
            <p>全量重建索引，或仅增量同步新增内容。</p>
          </div>
        </div>

        <div class="kb-actions">
          <el-button
            type="primary"
            class="kb-build-btn"
            :loading="buildProgress.processing"
            @click="startBuild"
          >
            {{ buildProgress.processing ? '构建中...' : '全量构建' }}
          </el-button>
          <el-button
            class="kb-build-btn kb-build-btn--ghost"
            :loading="buildProgress.processing"
            @click="startIncrementalBuild"
          >
            增量构建
          </el-button>
        </div>

        <div v-if="buildProgress.processing" class="kb-progress">
          <div class="kb-progress__top">
            <span class="kb-progress__label">{{ buildProgress.current_file || '正在处理文档块...' }}</span>
            <span class="kb-progress__pct">{{ progressPercentage }}%</span>
          </div>
          <el-progress
            :percentage="progressPercentage"
            :show-text="false"
            :stroke-width="8"
          />
          <p class="kb-progress__meta">
            {{ buildProgress.progress }} / {{ buildProgress.total }} 文档块
          </p>
        </div>

        <div v-if="buildResult" :class="['kb-result', `is-${buildResult.type}`, 'appear']">
          <span class="kb-result__mark" aria-hidden="true">
            {{ buildResult.type === 'success' ? '✓' : '!' }}
          </span>
          <span>{{ buildResult.message }}</span>
        </div>

        <div v-else-if="!buildProgress.processing" class="kb-hint">
          <p>建议在上传新文档后执行增量构建；结构大幅变更时再使用全量构建。</p>
        </div>
      </section>
    </div>

    <div v-show="kbTab === 'files'" class="kb-grid kb-grid--files" role="tabpanel">
      <section class="kb-panel">
        <div class="kb-panel__head kb-panel__head--row">
          <div>
            <h3>源文件</h3>
            <p>浏览、新建与删除知识库目录中的文档。</p>
          </div>
          <div class="kb-toolbar">
            <el-button size="small" type="primary" @click="showCreateFile">新建</el-button>
            <el-button size="small" @click="loadFileList">刷新</el-button>
          </div>
        </div>

        <div v-if="newFileVisible" class="kb-new-file">
          <el-input
            v-model="newFileName"
            placeholder="文件名（如 notes.md）"
            size="small"
            @keyup.enter="createNewFile"
          />
          <div class="kb-new-file__actions">
            <el-button size="small" type="primary" @click="createNewFile">创建</el-button>
            <el-button size="small" @click="newFileVisible = false">取消</el-button>
          </div>
        </div>

        <div v-if="fileListLoading" class="kb-empty">加载中...</div>
        <div v-else-if="fileList.length === 0" class="kb-empty">
          <p class="kb-empty__title">文档目录为空</p>
          <p class="kb-empty__desc">上传或新建文件后开始使用</p>
        </div>
        <div v-else class="kb-file-list">
          <button
            v-for="f in fileList"
            :key="f.name"
            type="button"
            class="kb-file-row"
            :class="{ 'is-active': editingFile && editingFile.name === f.name }"
            @click="openFile(f.name)"
          >
            <span class="kb-file-row__ext" aria-hidden="true">{{ getFileExtLabel(f.ext || f.name) }}</span>
            <span class="kb-file-row__body">
              <span class="kb-file-row__name">{{ f.name }}</span>
              <span class="kb-file-row__meta">
                {{ formatFileSize(f.size) }} · {{ formatTime(f.modified * 1000) }}
              </span>
            </span>
            <span
              class="kb-file-row__delete"
              title="删除文件"
              role="button"
              tabindex="0"
              @click.stop="confirmDeleteFile(f.name)"
              @keydown.enter.stop.prevent="confirmDeleteFile(f.name)"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 002 2h6a2 2 0 002-2l1-12M9 7V5a2 2 0 012-2h2a2 2 0 012 2v2" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </span>
          </button>
        </div>
      </section>

      <section v-if="editingFile" class="kb-panel kb-editor">
        <div class="kb-panel__head kb-panel__head--row">
          <div>
            <h3>{{ editingFile.name }}</h3>
            <p v-if="editorMode === 'preview'">Markdown 格式预览，切换到编辑可修改源文件。</p>
            <p v-else>直接编辑源文件内容，保存后生效。</p>
          </div>
          <div class="kb-toolbar">
            <div v-if="isEditingMarkdown" class="kb-editor__mode" role="tablist">
              <button
                type="button"
                role="tab"
                class="kb-editor__mode-btn"
                :class="{ 'is-active': editorMode === 'preview' }"
                :aria-selected="editorMode === 'preview'"
                @click="editorMode = 'preview'"
              >预览</button>
              <button
                type="button"
                role="tab"
                class="kb-editor__mode-btn"
                :class="{ 'is-active': editorMode === 'edit' }"
                :aria-selected="editorMode === 'edit'"
                @click="editorMode = 'edit'"
              >编辑</button>
            </div>
            <el-button
              v-if="editorMode === 'edit' || !isEditingMarkdown"
              size="small"
              type="primary"
              :loading="fileSaving"
              @click="saveFile"
            >保存</el-button>
            <el-button size="small" @click="closeEditor">关闭</el-button>
          </div>
        </div>

        <div
          v-if="editorMode === 'preview' && isEditingMarkdown"
          class="kb-md-preview"
          v-html="renderedMarkdown"
        />
        <el-input
          v-else
          v-model="editingFile.content"
          type="textarea"
          :rows="18"
          class="kb-editor__textarea"
          spellcheck="false"
        />

        <div v-if="fileSaveMsg" :class="['kb-result', `is-${fileSaveMsg.type}`]">
          {{ fileSaveMsg.text }}
        </div>
      </section>

      <section v-else class="kb-panel kb-editor-placeholder">
        <div class="kb-empty">
          <p class="kb-empty__title">选择一个文件开始编辑</p>
          <p class="kb-empty__desc">从左侧列表打开文档，或新建空白文件</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { API_BASE } from '../utils/api'
import { isMarkdownFile, renderMarkdown } from '../utils/markdown'

export default {
  name: 'KnowledgeView',
  data() {
    return {
      kbTab: 'upload',
      status: { vector_store_loaded: false },
      uploadedFiles: [],
      buildProgress: { processing: false, progress: 0, total: 0, current_file: '', status: '' },
      buildResult: null,
      progressInterval: null,
      fileList: [],
      fileListLoading: false,
      editingFile: null,
      editorMode: 'preview',
      fileSaving: false,
      fileSaveMsg: null,
      newFileVisible: false,
      newFileName: '',
      isDragOver: false
    }
  },
  computed: {
    progressPercentage() {
      if (!this.buildProgress.total) return 0
      return Math.round((this.buildProgress.progress / this.buildProgress.total) * 100)
    },
    isEditingMarkdown() {
      return !!this.editingFile && isMarkdownFile(this.editingFile.name)
    },
    renderedMarkdown() {
      if (!this.editingFile) return ''
      return renderMarkdown(this.editingFile.content)
    }
  },
  mounted() {
    this.fetchStatus()
    this.$nextTick(() => this.setupDragDrop())
  },
  beforeUnmount() {
    if (this.progressInterval) clearInterval(this.progressInterval)
    this.teardownDragDrop()
  },
  methods: {
    async fetchStatus() {
      try {
        const res = await axios.get(`${API_BASE}/status`)
        this.status = res.data
      } catch (e) {
        console.error(e)
      }
    },
    triggerFileInput() {
      this.$refs.fileInput.click()
    },
    setupDragDrop() {
      const uploadBox = this.$refs.uploadBox
      if (!uploadBox) return
      this.teardownDragDrop()
      this._dragOverHandler = (e) => {
        e.preventDefault()
        this.isDragOver = true
      }
      this._dragLeaveHandler = () => {
        this.isDragOver = false
      }
      this._dropHandler = async (e) => {
        e.preventDefault()
        this.isDragOver = false
        for (const file of e.dataTransfer.files) {
          await this.uploadFile(file)
        }
      }
      uploadBox.addEventListener('dragover', this._dragOverHandler)
      uploadBox.addEventListener('dragleave', this._dragLeaveHandler)
      uploadBox.addEventListener('drop', this._dropHandler)
    },
    teardownDragDrop() {
      const uploadBox = this.$refs.uploadBox
      if (!uploadBox) return
      if (this._dragOverHandler) uploadBox.removeEventListener('dragover', this._dragOverHandler)
      if (this._dragLeaveHandler) uploadBox.removeEventListener('dragleave', this._dragLeaveHandler)
      if (this._dropHandler) uploadBox.removeEventListener('drop', this._dropHandler)
    },
    async handleFileSelect(e) {
      for (const file of e.target.files) {
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
          this.uploadedFiles.push({ name: res.data.filename, size: res.data.size })
          ElMessage.success(`文件 ${file.name} 上传成功`)
        }
      } catch (e) {
        ElMessage.error(`上传失败: ${e.response?.data?.detail || e.message}`)
      }
    },
    formatFileSize(bytes) {
      if (!bytes && bytes !== 0) return ''
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1)
      return `${Math.round((bytes / Math.pow(k, i)) * 100) / 100} ${sizes[i]}`
    },
    formatTime(timestamp) {
      if (!timestamp) return ''
      return new Date(timestamp).toLocaleString('zh-CN')
    },
    getFileExtLabel(type) {
      if (!type) return 'FILE'
      const raw = String(type).toLowerCase()
      const ext = raw.includes('.') ? raw.split('.').pop() : raw.replace(/^\./, '')
      return (ext || 'file').slice(0, 4).toUpperCase()
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
    startProgressPolling() {
      if (this.progressInterval) clearInterval(this.progressInterval)
      this.buildResult = null
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
                message: `知识库构建成功，共处理 ${res.data.total} 个文档块`
              }
              await this.fetchStatus()
            } else if (res.data.status === 'error') {
              this.buildResult = {
                type: 'error',
                message: `构建失败: ${res.data.current_file}`
              }
            }
          }
        } catch (e) {
          console.error('获取进度失败:', e)
        }
      }, 500)
    },
    switchToFilesTab() {
      this.kbTab = 'files'
      this.loadFileList()
    },
    async loadFileList() {
      this.fileListLoading = true
      try {
        const res = await axios.get(`${API_BASE}/files`)
        if (res.data.success) this.fileList = res.data.files
      } catch {
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
          this.editorMode = isMarkdownFile(res.data.name) ? 'preview' : 'edit'
          this.fileSaveMsg = null
        }
      } catch (e) {
        ElMessage.error(`打开文件失败: ${e.response?.data?.detail || e.message}`)
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
          this.fileSaveMsg = { type: 'success', text: '已保存' }
          this.loadFileList()
          setTimeout(() => { this.fileSaveMsg = null }, 2000)
        }
      } catch (e) {
        this.fileSaveMsg = { type: 'error', text: `保存失败: ${e.response?.data?.detail || e.message}` }
      } finally {
        this.fileSaving = false
      }
    },
    closeEditor() {
      if (this.editingFile && this.editingFile.content !== this.editingFile.originalContent) {
        if (!confirm('文件有未保存的修改，确定关闭？')) return
      }
      this.editingFile = null
      this.editorMode = 'preview'
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
        ElMessage.error(`创建失败: ${e.response?.data?.detail || e.message}`)
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
          if (this.editingFile?.name === filename) this.editingFile = null
          this.loadFileList()
        }
      } catch (e) {
        if (e !== 'cancel') {
          ElMessage.error(`删除失败: ${e.response?.data?.detail || e.message}`)
        }
      }
    }
  }
}
</script>

<style scoped>
.kb-page {
  max-width: none;
}

.kb-hero {
  align-items: flex-end;
  margin-bottom: 22px;
}

.kb-hero__aside {
  flex-shrink: 0;
}

.kb-status {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 168px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.55), rgba(255, 255, 255, 0.22)),
    var(--bg-glass);
  box-shadow: var(--shadow-sm);
  backdrop-filter: var(--glass-blur);
}

.kb-status__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--warning);
  box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.12);
}

.kb-status.is-ready .kb-status__dot {
  background: var(--success);
  box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.14);
}

.kb-status__label {
  display: block;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.kb-status__value {
  display: block;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  line-height: 1.2;
}

.kb-status.is-ready .kb-status__value {
  color: var(--success);
}

.kb-segment {
  display: inline-flex;
  padding: 4px;
  margin-bottom: 18px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: rgba(148, 163, 184, 0.08);
  gap: 4px;
}

.kb-segment__item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
  padding: 9px 16px;
  border-radius: 10px;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast), box-shadow var(--transition-fast);
}

.kb-segment__item svg {
  width: 16px;
  height: 16px;
}

.kb-segment__item:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.55);
}

.kb-segment__item.is-active {
  color: var(--text-primary);
  background: #fff;
  box-shadow: var(--shadow-sm);
}

.kb-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.kb-grid--files {
  grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
}

.kb-panel {
  padding: 22px 24px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: var(--bg-glass);
  backdrop-filter: var(--glass-blur);
  box-shadow: var(--shadow-sm);
  min-height: 320px;
}

.kb-panel__head {
  margin-bottom: 18px;
}

.kb-panel__head--row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.kb-panel__head h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

.kb-panel__head p {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-muted);
}

.kb-toolbar {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.kb-file-input {
  display: none;
}

.kb-dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 180px;
  padding: 28px 20px;
  border-radius: 16px;
  border: 1.5px dashed rgba(100, 116, 139, 0.35);
  background: rgba(148, 163, 184, 0.06);
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    transform var(--transition-fast),
    box-shadow var(--transition-fast);
}

.kb-dropzone:hover,
.kb-dropzone.is-dragover {
  border-color: rgba(99, 102, 241, 0.55);
  background: rgba(99, 102, 241, 0.06);
  box-shadow: inset 0 0 0 1px rgba(99, 102, 241, 0.08);
}

.kb-dropzone.is-dragover {
  transform: scale(1.01);
}

.kb-dropzone__icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--border-color);
}

.kb-dropzone__icon svg {
  width: 28px;
  height: 28px;
}

.kb-dropzone__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.kb-dropzone__hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
  letter-spacing: 0.04em;
}

.kb-upload-list {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 180px;
  overflow: auto;
}

.kb-upload-list__head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-muted);
  padding: 0 2px;
}

.kb-upload-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--border-light);
  background: rgba(255, 255, 255, 0.55);
}

.kb-upload-item__icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: var(--text-secondary);
  background: rgba(148, 163, 184, 0.12);
  flex-shrink: 0;
}

.kb-upload-item__icon svg {
  width: 14px;
  height: 14px;
}

.kb-upload-item__name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-upload-item__size {
  font-size: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.kb-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.kb-build-btn {
  width: 100% !important;
  height: 44px !important;
  margin: 0 !important;
  font-size: 14px !important;
  border-radius: 12px !important;
}

.kb-build-btn--ghost {
  background: rgba(255, 255, 255, 0.6) !important;
  border: 1px solid var(--border-color) !important;
  color: var(--text-primary) !important;
  box-shadow: none !important;
}

.kb-build-btn--ghost:hover {
  border-color: rgba(99, 102, 241, 0.35) !important;
  color: var(--primary-dark) !important;
}

.kb-progress {
  margin-top: 18px;
  padding: 16px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.45);
}

.kb-progress__top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.kb-progress__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-progress__pct {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  flex-shrink: 0;
}

.kb-progress__meta {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}

.kb-hint {
  margin-top: 18px;
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(148, 163, 184, 0.08);
  border: 1px solid var(--border-light);
}

.kb-hint p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-muted);
}

.kb-result {
  margin-top: 16px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
}

.kb-result__mark {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 12px;
  flex-shrink: 0;
}

.kb-result.is-success {
  color: #047857;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.kb-result.is-success .kb-result__mark {
  background: rgba(16, 185, 129, 0.18);
}

.kb-result.is-error {
  color: #b91c1c;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.kb-result.is-error .kb-result__mark {
  background: rgba(239, 68, 68, 0.16);
}

.kb-new-file {
  margin-bottom: 14px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(99, 102, 241, 0.05);
  border: 1px solid rgba(99, 102, 241, 0.12);
}

.kb-new-file__actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.kb-file-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 460px;
  overflow: auto;
}

.kb-file-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  text-align: left;
  padding: 11px 12px;
  border-radius: 12px;
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  color: inherit;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}

.kb-file-row:hover {
  background: rgba(148, 163, 184, 0.1);
}

.kb-file-row.is-active {
  background: rgba(99, 102, 241, 0.08);
  border-color: rgba(99, 102, 241, 0.18);
}

.kb-file-row__ext {
  width: 42px;
  height: 28px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  background: rgba(148, 163, 184, 0.14);
  flex-shrink: 0;
}

.kb-file-row__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.kb-file-row__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-file-row__meta {
  font-size: 11px;
  color: var(--text-muted);
}

.kb-file-row__delete {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: var(--text-muted);
  opacity: 0;
  transition: opacity var(--transition-fast), background var(--transition-fast), color var(--transition-fast);
}

.kb-file-row:hover .kb-file-row__delete,
.kb-file-row.is-active .kb-file-row__delete {
  opacity: 1;
}

.kb-file-row__delete:hover {
  background: rgba(239, 68, 68, 0.1);
  color: var(--danger);
}

.kb-file-row__delete svg {
  width: 14px;
  height: 14px;
}

.kb-editor__mode {
  display: inline-flex;
  padding: 2px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.06);
  margin-right: 4px;
}

.kb-editor__mode-btn {
  border: 0;
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  padding: 6px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.kb-editor__mode-btn.is-active {
  background: #fff;
  color: var(--text-primary);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}

.kb-editor :deep(.kb-editor__textarea .el-textarea__inner) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
  border-radius: 12px;
  min-height: 380px;
  background: rgba(255, 255, 255, 0.55);
}

.kb-md-preview {
  min-height: 380px;
  max-height: min(70vh, 720px);
  overflow: auto;
  padding: 18px 20px;
  border-radius: 12px;
  border: 1px solid var(--border-subtle, rgba(15, 23, 42, 0.08));
  background: rgba(255, 255, 255, 0.72);
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.7;
}

.kb-md-preview :deep(:first-child) {
  margin-top: 0;
}

.kb-md-preview :deep(:last-child) {
  margin-bottom: 0;
}

.kb-md-preview :deep(h1),
.kb-md-preview :deep(h2),
.kb-md-preview :deep(h3),
.kb-md-preview :deep(h4) {
  margin: 1.15em 0 0.55em;
  line-height: 1.35;
  font-weight: 700;
  color: var(--text-primary);
}

.kb-md-preview :deep(h1) { font-size: 1.55em; }
.kb-md-preview :deep(h2) { font-size: 1.3em; border-bottom: 1px solid rgba(15, 23, 42, 0.08); padding-bottom: 0.3em; }
.kb-md-preview :deep(h3) { font-size: 1.12em; }

.kb-md-preview :deep(p),
.kb-md-preview :deep(ul),
.kb-md-preview :deep(ol),
.kb-md-preview :deep(blockquote),
.kb-md-preview :deep(pre),
.kb-md-preview :deep(table) {
  margin: 0.75em 0;
}

.kb-md-preview :deep(ul),
.kb-md-preview :deep(ol) {
  padding-left: 1.4em;
}

.kb-md-preview :deep(li + li) {
  margin-top: 0.25em;
}

.kb-md-preview :deep(strong) {
  font-weight: 700;
}

.kb-md-preview :deep(a) {
  color: var(--primary, #5b5bd6);
  text-decoration: none;
}

.kb-md-preview :deep(a:hover) {
  text-decoration: underline;
}

.kb-md-preview :deep(blockquote) {
  margin-left: 0;
  padding: 0.2em 0 0.2em 0.9em;
  border-left: 3px solid rgba(91, 91, 214, 0.45);
  color: var(--text-secondary);
}

.kb-md-preview :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.9em;
  padding: 0.12em 0.35em;
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.06);
}

.kb-md-preview :deep(pre) {
  padding: 12px 14px;
  border-radius: 10px;
  overflow: auto;
  background: rgba(15, 23, 42, 0.05);
}

.kb-md-preview :deep(pre code) {
  padding: 0;
  background: transparent;
}

.kb-md-preview :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  overflow: hidden;
  border-radius: 8px;
}

.kb-md-preview :deep(th),
.kb-md-preview :deep(td) {
  border: 1px solid rgba(15, 23, 42, 0.1);
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
}

.kb-md-preview :deep(th) {
  background: rgba(15, 23, 42, 0.04);
  font-weight: 650;
}

.kb-md-preview :deep(tr:nth-child(even) td) {
  background: rgba(15, 23, 42, 0.02);
}

.kb-md-preview :deep(hr) {
  border: 0;
  border-top: 1px solid rgba(15, 23, 42, 0.1);
  margin: 1.2em 0;
}

.kb-editor-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
}

.kb-empty {
  padding: 36px 16px;
  text-align: center;
  color: var(--text-muted);
}

.kb-empty__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
}

.kb-empty__desc {
  margin: 6px 0 0;
  font-size: 12px;
}

.dark .kb-status,
.dark .kb-panel,
.dark .kb-upload-item,
.dark .kb-progress {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.03), transparent),
    var(--bg-glass);
}

.dark .kb-segment {
  background: rgba(255, 255, 255, 0.04);
}

.dark .kb-segment__item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.dark .kb-segment__item.is-active {
  background: rgba(37, 37, 66, 0.95);
  color: var(--text-primary);
}

.dark .kb-dropzone {
  background: rgba(255, 255, 255, 0.03);
}

.dark .kb-dropzone__icon,
.dark .kb-build-btn--ghost {
  background: rgba(255, 255, 255, 0.04) !important;
}

.dark .kb-hint,
.dark .kb-file-row:hover {
  background: rgba(255, 255, 255, 0.04);
}

.dark .kb-editor :deep(.kb-editor__textarea .el-textarea__inner) {
  background: rgba(15, 15, 26, 0.55);
  color: var(--text-primary);
}

.dark .kb-editor__mode {
  background: rgba(255, 255, 255, 0.06);
}

.dark .kb-editor__mode-btn.is-active {
  background: rgba(37, 37, 66, 0.95);
  color: var(--text-primary);
  box-shadow: none;
}

.dark .kb-md-preview {
  background: rgba(15, 15, 26, 0.55);
  border-color: rgba(255, 255, 255, 0.08);
}

.dark .kb-md-preview :deep(h2) {
  border-bottom-color: rgba(255, 255, 255, 0.08);
}

.dark .kb-md-preview :deep(code),
.dark .kb-md-preview :deep(pre),
.dark .kb-md-preview :deep(th) {
  background: rgba(255, 255, 255, 0.06);
}

.dark .kb-md-preview :deep(th),
.dark .kb-md-preview :deep(td) {
  border-color: rgba(255, 255, 255, 0.1);
}

.dark .kb-md-preview :deep(tr:nth-child(even) td) {
  background: rgba(255, 255, 255, 0.03);
}

.dark .kb-md-preview :deep(hr) {
  border-top-color: rgba(255, 255, 255, 0.1);
}

@media (max-width: 960px) {
  .kb-grid,
  .kb-grid--files {
    grid-template-columns: 1fr;
  }

  .kb-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .kb-segment {
    width: 100%;
  }

  .kb-segment__item {
    flex: 1;
    justify-content: center;
  }

  .kb-panel__head--row {
    flex-direction: column;
  }
}
</style>
