<template>
  <div class="page-shell settings-page">
    <div class="page-hero settings-hero">
      <div>
        <p class="page-eyebrow">Model Access</p>
        <h2 class="page-title">模型配置</h2>
        <p class="page-desc">统一管理模型连接与调用方式，配置会实时保存到本机浏览器。</p>
      </div>
      <div class="settings-hero__aside">
        <div class="settings-live">
          <span class="settings-live__dot" />
          <span>本地已同步</span>
        </div>
        <div class="settings-status">
          <span class="settings-status__label">当前提供者</span>
          <span class="settings-status__value">{{ currentProviderLabel }}</span>
          <span class="settings-status__meta">{{ currentProviderMeta }}</span>
        </div>
      </div>
    </div>

    <section class="settings-section">
      <div class="settings-section__head">
        <div>
          <h3>选择模型来源</h3>
          <p>先确定接入方式，再填写对应参数。本地与云端可随时切换。</p>
        </div>
      </div>

      <div class="provider-grid" role="listbox" :aria-activedescendant="`provider-${provider || 'default'}`">
        <button
          v-for="(opt, index) in providerCards"
          :id="`provider-${opt.value || 'default'}`"
          :key="opt.value || 'default'"
          type="button"
          role="option"
          class="provider-card"
          :class="{ 'is-active': provider === opt.value }"
          :style="{ '--delay': `${index * 50}ms` }"
          :aria-selected="provider === opt.value"
          @click="selectProvider(opt.value)"
        >
          <div class="provider-card__top">
            <span class="provider-card__icon" :data-tone="opt.tone" aria-hidden="true">{{ opt.icon }}</span>
            <span v-if="provider === opt.value" class="provider-card__check" aria-hidden="true">✓</span>
          </div>
          <span class="provider-card__name">{{ opt.label }}</span>
          <span class="provider-card__desc">{{ opt.desc }}</span>
        </button>
      </div>
    </section>

    <section v-if="provider === 'ollama'" class="settings-section settings-section--detail appear">
      <div class="settings-section__head">
        <div>
          <h3>Ollama 本地配置</h3>
          <p>适用于本机或内网部署，强调隐私与可控性。</p>
        </div>
        <span class="settings-badge settings-badge--local">本地</span>
      </div>

      <div class="settings-form">
        <div class="settings-field">
          <label class="settings-label" for="ollama-model">模型名称</label>
          <p class="settings-field-hint">与 ollama list 中的名称保持一致</p>
          <el-input
            id="ollama-model"
            v-model="ollamaModel"
            placeholder="例如: gemma3:4b"
            clearable
            @change="saveSettings"
          />
        </div>
        <div class="settings-field">
          <label class="settings-label" for="ollama-url">服务地址</label>
          <p class="settings-field-hint">默认本地端口，也可指向内网节点</p>
          <el-input
            id="ollama-url"
            v-model="ollamaApiUrl"
            placeholder="例如: http://localhost:11434"
            clearable
            @change="saveSettings"
          />
        </div>
      </div>
    </section>

    <section v-else-if="provider === 'deepseek'" class="settings-section settings-section--detail appear">
      <div class="settings-section__head">
        <div>
          <h3>DeepSeek 远程配置</h3>
          <p>适用于云端推理，请确认模型版本、网关地址与密钥。</p>
        </div>
        <span class="settings-badge settings-badge--cloud">云端</span>
      </div>

      <div class="settings-form">
        <div class="settings-field">
          <label class="settings-label" for="deepseek-model">模型名称</label>
          <p class="settings-field-hint">推荐使用官方稳定版本</p>
          <el-input
            id="deepseek-model"
            v-model="deepseekModel"
            placeholder="例如: deepseek-v1"
            clearable
            @change="saveSettings"
          />
        </div>
        <div class="settings-form-grid">
          <div class="settings-field">
            <label class="settings-label" for="deepseek-url">API URL</label>
            <p class="settings-field-hint">官方或自建网关地址</p>
            <el-input
              id="deepseek-url"
              v-model="deepseekApiUrl"
              placeholder="例如: https://api.deepseek.com"
              clearable
              @change="saveSettings"
            />
          </div>
          <div class="settings-field">
            <label class="settings-label" for="deepseek-key">API Key</label>
            <p class="settings-field-hint">仅保存在当前浏览器</p>
            <el-input
              id="deepseek-key"
              v-model="deepseekApiKey"
              placeholder="请输入 DeepSeek API Key"
              show-password
              clearable
              @change="saveSettings"
            />
          </div>
        </div>
      </div>
    </section>

    <section v-else class="settings-section settings-section--hint appear">
      <div class="settings-hint-card">
        <div class="settings-hint-card__icon" aria-hidden="true">{{ hintIcon }}</div>
        <div>
          <h4>{{ hintTitle }}</h4>
          <p>{{ hintDesc }}</p>
        </div>
      </div>
    </section>

    <aside class="settings-footnote">
      <div class="settings-footnote__icon" aria-hidden="true">💾</div>
      <div>
        <strong>本地保存说明</strong>
        <p>模型配置会实时写入当前浏览器本地存储，适合个人设备或受控终端环境。更换浏览器或清理站点数据后需重新配置。</p>
      </div>
    </aside>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'

export default {
  name: 'SettingsView',
  data() {
    return {
      provider: '',
      ollamaModel: '',
      ollamaApiUrl: '',
      deepseekModel: '',
      deepseekApiUrl: '',
      deepseekApiKey: '',
      providerCards: [
        {
          value: '',
          label: '后端默认',
          desc: '沿用服务端环境变量与部署配置',
          icon: '◎',
          tone: 'default',
          meta: '跟随部署配置'
        },
        {
          value: 'ollama',
          label: 'Ollama',
          desc: '本机 / 内网推理，数据不出域',
          icon: '⬡',
          tone: 'local',
          meta: '本地隐私优先'
        },
        {
          value: 'deepseek',
          label: 'DeepSeek',
          desc: '云端高性价比推理接口',
          icon: '◈',
          tone: 'cloud',
          meta: '远程 API 接入'
        },
        {
          value: 'openai',
          label: 'OpenAI',
          desc: '兼容 OpenAI 协议的模型服务',
          icon: '◉',
          tone: 'openai',
          meta: '协议兼容接入'
        },
        {
          value: 'gemini',
          label: 'Gemini',
          desc: 'Google Gemini 系列模型',
          icon: '✦',
          tone: 'gemini',
          meta: '多模态云端'
        }
      ]
    }
  },
  computed: {
    currentProvider() {
      return this.providerCards.find((o) => o.value === this.provider) || this.providerCards[0]
    },
    currentProviderLabel() {
      return this.currentProvider.label
    },
    currentProviderMeta() {
      return this.currentProvider.meta
    },
    hintIcon() {
      const map = { '': '⚙️', openai: '🔗', gemini: '✦' }
      return map[this.provider] ?? '⚙️'
    },
    hintTitle() {
      if (this.provider === 'openai') return 'OpenAI 兼容接入'
      if (this.provider === 'gemini') return 'Gemini 接入'
      return '使用后端默认配置'
    },
    hintDesc() {
      if (this.provider === 'openai') {
        return '当前选择将走 OpenAI 兼容协议。密钥与端点由后端环境变量管理，前端无需额外填写。'
      }
      if (this.provider === 'gemini') {
        return '当前选择将使用 Gemini 系列模型。凭据由服务端配置，切换后即可在对话中生效。'
      }
      return '未指定前端覆盖时，将使用服务端默认模型提供者与参数，适合统一运维的部署环境。'
    }
  },
  mounted() {
    this.loadSettings()
  },
  methods: {
    loadSettings() {
      const saved = localStorage.getItem('ragSettings')
      if (!saved) return
      try {
        const settings = JSON.parse(saved)
        this.provider = settings.provider || ''
        this.ollamaModel = settings.ollamaModel || ''
        this.ollamaApiUrl = settings.ollamaApiUrl || ''
        this.deepseekModel = settings.deepseekModel || ''
        this.deepseekApiUrl = settings.deepseekApiUrl || ''
        this.deepseekApiKey = settings.deepseekApiKey || ''
      } catch {
        // ignore
      }
    },
    saveSettings() {
      const saved = JSON.parse(localStorage.getItem('ragSettings') || '{}')
      localStorage.setItem('ragSettings', JSON.stringify({
        ...saved,
        provider: this.provider,
        ollamaModel: this.ollamaModel,
        ollamaApiUrl: this.ollamaApiUrl,
        deepseekModel: this.deepseekModel,
        deepseekApiUrl: this.deepseekApiUrl,
        deepseekApiKey: this.deepseekApiKey
      }))
      window.dispatchEvent(new CustomEvent('rag-settings-changed'))
    },
    selectProvider(value) {
      if (this.provider === value) return
      this.provider = value
      this.saveSettings()
      ElMessage.success(`已切换到 ${this.currentProviderLabel}`)
    }
  }
}
</script>

<style scoped>
.settings-page {
  max-width: 1080px;
}

.settings-hero {
  align-items: flex-end;
  margin-bottom: 28px;
}

.settings-hero__aside {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
  flex-shrink: 0;
}

.settings-live {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-glass);
  color: var(--text-secondary);
  font-size: 12px;
  backdrop-filter: var(--glass-blur);
}

.settings-live__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--success);
  box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.45);
  animation: settingsPulse 2s ease-out infinite;
}

.settings-status {
  min-width: 180px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.55), rgba(255, 255, 255, 0.22)),
    var(--bg-glass);
  box-shadow: var(--shadow-sm);
  backdrop-filter: var(--glass-blur);
  text-align: right;
}

.settings-status__label {
  display: block;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 6px;
}

.settings-status__value {
  display: block;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  line-height: 1.2;
}

.settings-status__meta {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-muted);
}

.settings-section {
  margin-bottom: 20px;
  padding: 22px 24px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: var(--bg-glass);
  backdrop-filter: var(--glass-blur);
  box-shadow: var(--shadow-sm);
}

.settings-section__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.settings-section__head h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.settings-section__head p {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-muted);
  max-width: 520px;
}

.settings-badge {
  flex-shrink: 0;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.settings-badge--local {
  color: #047857;
  background: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.settings-badge--cloud {
  color: #1d4ed8;
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.provider-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.provider-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  min-height: 148px;
  padding: 16px 14px 14px;
  border-radius: 16px;
  border: 1px solid var(--border-light);
  background: rgba(148, 163, 184, 0.06);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    transform var(--transition-fast),
    box-shadow var(--transition-fast);
  animation: settingsRise 0.4s ease both;
  animation-delay: var(--delay);
}

.provider-card:hover {
  border-color: rgba(99, 102, 241, 0.28);
  background: rgba(99, 102, 241, 0.06);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.provider-card.is-active {
  border-color: rgba(99, 102, 241, 0.4);
  background:
    linear-gradient(160deg, rgba(99, 102, 241, 0.12), rgba(236, 72, 153, 0.06));
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.12);
}

.provider-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  margin-bottom: 4px;
}

.provider-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 700;
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-secondary);
}

.provider-card__icon[data-tone='local'] {
  background: rgba(16, 185, 129, 0.14);
  color: #059669;
}

.provider-card__icon[data-tone='cloud'] {
  background: rgba(59, 130, 246, 0.14);
  color: #2563eb;
}

.provider-card__icon[data-tone='openai'] {
  background: rgba(16, 185, 129, 0.12);
  color: #0f766e;
}

.provider-card__icon[data-tone='gemini'] {
  background: rgba(245, 158, 11, 0.14);
  color: #d97706;
}

.provider-card__icon[data-tone='default'] {
  background: rgba(99, 102, 241, 0.12);
  color: var(--primary);
}

.provider-card__check {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  background: var(--gradient-primary);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
}

.provider-card__name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.provider-card__desc {
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-muted);
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.settings-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.settings-label {
  display: block;
  margin-bottom: 0;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.02em;
}

.settings-field-hint {
  margin: 4px 0 10px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-muted);
}

.settings-section--hint {
  padding: 0;
  border: none;
  background: transparent;
  box-shadow: none;
  backdrop-filter: none;
}

.settings-hint-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 18px 20px;
  border-radius: 16px;
  border: 1px dashed rgba(99, 102, 241, 0.28);
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.06), rgba(236, 72, 153, 0.04));
}

.settings-hint-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  flex-shrink: 0;
  background: rgba(99, 102, 241, 0.1);
  font-size: 18px;
}

.settings-hint-card h4 {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.settings-hint-card p {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-secondary);
}

.settings-footnote {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-top: 8px;
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: rgba(148, 163, 184, 0.06);
}

.settings-footnote__icon {
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: rgba(148, 163, 184, 0.12);
  font-size: 15px;
}

.settings-footnote strong {
  display: block;
  font-size: 13px;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.settings-footnote p {
  margin: 0;
  font-size: 12px;
  line-height: 1.65;
  color: var(--text-muted);
}

.appear {
  animation: settingsRise 0.35s ease both;
}

@keyframes settingsRise {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes settingsPulse {
  0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.45); }
  70% { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
  100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}

:deep(.el-input__wrapper) {
  border-radius: 12px !important;
  box-shadow: 0 0 0 1px var(--border-color) inset !important;
  background: rgba(255, 255, 255, 0.72) !important;
  padding: 4px 12px !important;
  transition: box-shadow var(--transition-fast) !important;
}

:deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.35) inset !important;
}

:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--primary) inset, 0 0 0 3px var(--primary-glow) !important;
}

:deep(.el-input__wrapper) {
  min-height: 42px;
}

.dark .settings-status {
  background:
    linear-gradient(180deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.72)),
    var(--bg-glass);
}

.dark .provider-card {
  background: rgba(129, 140, 248, 0.05);
}

.dark .provider-card:hover,
.dark .provider-card.is-active {
  background: linear-gradient(160deg, rgba(129, 140, 248, 0.16), rgba(244, 114, 182, 0.08));
}

.dark .settings-hint-card {
  border-color: rgba(129, 140, 248, 0.28);
  background: linear-gradient(135deg, rgba(129, 140, 248, 0.1), rgba(244, 114, 182, 0.06));
}

.dark .settings-footnote {
  background: rgba(129, 140, 248, 0.06);
}

.dark .settings-badge--local {
  color: #6ee7b7;
  background: rgba(16, 185, 129, 0.16);
}

.dark .settings-badge--cloud {
  color: #93c5fd;
  background: rgba(59, 130, 246, 0.16);
}

.dark :deep(.el-input__wrapper) {
  background: rgba(15, 23, 42, 0.72) !important;
}

@media (max-width: 1100px) {
  .provider-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .settings-hero {
    flex-direction: column;
    align-items: stretch;
  }

  .settings-hero__aside {
    align-items: stretch;
  }

  .settings-status {
    text-align: left;
  }

  .provider-grid,
  .settings-form-grid {
    grid-template-columns: 1fr;
  }

  .provider-card {
    min-height: 0;
  }
}
</style>
