"""
诊断 LLM 生成失败问题
"""

from config import Config
from rag_assistant import RAGAssistant
from vector_store import VectorStore
import traceback

def check_llm_config():
    """检查 LLM 配置"""
    print("\n" + "="*70)
    print("【步骤1】检查 LLM 配置")
    print("="*70 + "\n")
    
    print(f"MODEL_PROVIDER: {Config.MODEL_PROVIDER}")
    print(f"LLM_MODEL: {Config.LLM_MODEL}")
    print(f"TEMPERATURE: {Config.TEMPERATURE}")
    print(f"MAX_TOKENS: {Config.MAX_TOKENS}")
    
    if Config.MODEL_PROVIDER == "openai":
        print(f"OPENAI_API_KEY: {'已设置' if Config.OPENAI_API_KEY else '❌ 未设置'}")
        print(f"OPENAI_API_BASE: {Config.OPENAI_API_BASE}")
    elif Config.MODEL_PROVIDER == "gemini":
        print(f"GEMINI_API_KEY: {'已设置' if Config.GEMINI_API_KEY else '❌ 未设置'}")
    elif Config.MODEL_PROVIDER == "ollama":
        print(f"OLLAMA_API_URL: {Config.OLLAMA_API_URL}")
        print(f"OLLAMA_MODEL: {Config.OLLAMA_MODEL}")
    
    return Config.MODEL_PROVIDER


def test_llm_directly():
    """直接测试 LLM"""
    print("\n" + "="*70)
    print("【步骤2】直接测试 LLM 生成")
    print("="*70 + "\n")
    
    try:
        from langchain.chat_models import init_chat_model
        
        print(f"初始化 LLM: {Config.LLM_MODEL}")
        llm = init_chat_model(
            Config.LLM_MODEL,
            temperature=Config.TEMPERATURE,
            max_tokens=Config.MAX_TOKENS,
        )
        
        print("✓ LLM 初始化成功\n")
        
        # 测试简单生成
        print("测试简单提示...")
        response = llm.invoke("Hello, how are you?")
        print(f"✓ LLM 响应成功: {str(response.content)[:100]}...\n")
        
        return True
        
    except Exception as e:
        print(f"❌ LLM 测试失败:")
        print(f"   错误: {e}\n")
        traceback.print_exc()
        return False


def test_retrieval_only():
    """仅测试检索，不涉及 LLM"""
    print("\n" + "="*70)
    print("【步骤3】测试检索功能（不需要 LLM）")
    print("="*70 + "\n")
    
    try:
        vector_store = VectorStore()
        query = "深度学习的主要架构"
        
        print(f"查询: {query}\n")
        docs = vector_store.similarity_search(query, k=3)
        
        print(f"✓ 找到 {len(docs)} 个文档\n")
        
        for i, doc in enumerate(docs, 1):
            content = doc.page_content[:100].replace('\n', ' ')
            source = doc.metadata.get('source', '未知')
            print(f"  [{i}] {source}")
            print(f"      {content}...\n")
        
        return len(docs) > 0
        
    except Exception as e:
        print(f"❌ 检索失败: {e}\n")
        traceback.print_exc()
        return False


def test_rag_with_fallback():
    """测试 RAG，观察回退行为"""
    print("\n" + "="*70)
    print("【步骤4】测试 RAG 查询（观察回退）")
    print("="*70 + "\n")
    
    try:
        assistant = RAGAssistant()
        query = "深度学习的主要架构"
        
        print(f"查询: {query}\n")
        result = assistant.query(query, return_sources=True, method='vector', k=3)
        
        print(f"答案: {result.get('answer', '无答案')[:200]}...\n")
        
        if 'error' in result:
            print(f"错误信息: {result['error']}\n")
        
        if 'sources' in result:
            print(f"来源数量: {len(result['sources'])}")
            for i, doc in enumerate(result['sources'][:2], 1):
                try:
                    if hasattr(doc, 'page_content'):
                        content = doc.page_content[:80].replace('\n', ' ')
                    else:
                        content = str(doc)[:80]
                    print(f"  [{i}] {content}...\n")
                except Exception as e:
                    print(f"  [{i}] 无法展示 ({e})\n")
        
        return result
        
    except Exception as e:
        print(f"❌ RAG 查询失败: {e}\n")
        traceback.print_exc()
        return None


def check_api_connectivity():
    """检查 API 连接"""
    print("\n" + "="*70)
    print("【步骤5】检查 API 连接")
    print("="*70 + "\n")
    
    provider = Config.MODEL_PROVIDER
    
    if provider == "openai":
        print("检查 OpenAI 连接...")
        try:
            import requests
            response = requests.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {Config.OPENAI_API_KEY}"},
                timeout=5
            )
            if response.status_code == 200:
                print(f"✓ OpenAI 连接成功 (HTTP {response.status_code})\n")
                return True
            else:
                print(f"❌ OpenAI 返回错误: HTTP {response.status_code}")
                print(f"   {response.text}\n")
                return False
        except Exception as e:
            print(f"❌ 连接失败: {e}\n")
            return False
    
    elif provider == "ollama":
        print("检查 Ollama 连接...")
        try:
            import requests
            response = requests.get(
                f"{Config.OLLAMA_API_URL}/api/tags",
                timeout=5
            )
            if response.status_code == 200:
                print(f"✓ Ollama 连接成功 (HTTP {response.status_code})\n")
                models = response.json().get('models', [])
                print(f"可用模型: {len(models)} 个")
                for model in models[:5]:
                    print(f"  • {model.get('name', '未知')}")
                print()
                return True
            else:
                print(f"❌ Ollama 返回错误: HTTP {response.status_code}\n")
                return False
        except Exception as e:
            print(f"❌ 连接失败: {e}\n")
            print("  提示: 确保 Ollama 已启动")
            print(f"  检查: curl -s {Config.OLLAMA_API_URL}/api/tags\n")
            return False
    
    else:
        print(f"不支持的 provider: {provider}\n")
        return False


def main():
    print("\n" + "="*80)
    print("LLM 生成失败诊断")
    print("="*80)
    
    # 检查配置
    provider = check_llm_config()
    
    # 检查 API 连接
    api_ok = check_api_connectivity()
    
    # 测试检索
    retrieval_ok = test_retrieval_only()
    
    # 测试 LLM
    llm_ok = test_llm_directly()
    
    # 测试 RAG
    rag_result = test_rag_with_fallback()
    
    # 总结
    print("\n" + "="*80)
    print("诊断总结")
    print("="*80 + "\n")
    
    print(f"API 连接: {'✅' if api_ok else '❌'}")
    print(f"检索功能: {'✅' if retrieval_ok else '❌'}")
    print(f"LLM 生成: {'✅' if llm_ok else '❌'}")
    
    if not llm_ok:
        print("\n【问题根源】")
        print("LLM 无法生成内容。可能的原因：")
        print("1. API 密钥无效或已过期")
        print("2. API 配额已用完")
        print("3. 网络连接问题")
        print("4. 模型名称不支持")
        print("\n【解决方案】")
        
        if provider == "openai":
            print("• 检查 .env 中的 OPENAI_API_KEY 是否正确")
            print("• 检查 API 余额是否充足")
            print("• 尝试更换模型: LLM_MODEL=gpt-3.5-turbo")
        elif provider == "ollama":
            print("• 检查 Ollama 服务是否正在运行")
            print("• 运行: ollama serve")
            print("• 或使用: LLM_MODEL=llama2")
        elif provider == "gemini":
            print("• 检查 .env 中的 GEMINI_API_KEY 是否正确")
            print("• 检查 API 配额")
    
    if retrieval_ok and not llm_ok:
        print("\n【好消息】")
        print("检索功能正常，只是 LLM 无法生成。")
        print("系统会显示检索到的参考文档作为回退。")
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
