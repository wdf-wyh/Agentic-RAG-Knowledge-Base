"""分析工具 - 让 Agent 具备文档分析和总结能力"""

from typing import List, Dict, Any, Optional
from pathlib import Path

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory
from src.config.settings import Config


class DocumentAnalysisTool(BaseTool):
    """文档结构分析工具
    
    分析知识库的文档结构，提供优化建议
    """
    
    def __init__(self, documents_path: str = None):
        self._documents_path = documents_path or "./documents"
        super().__init__()
    
    @property
    def name(self) -> str:
        return "analyze_documents"
    
    @property
    def description(self) -> str:
        return "分析知识库文档的结构和组织方式，识别问题并提供优化建议。"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "analysis_type",
                "type": "string",
                "description": "分析类型: 'structure'(目录结构), 'content'(内容质量), 'coverage'(覆盖度), 'all'(全部)，默认 'structure'",
                "required": False
            }
        ]
    
    def _analyze_structure(self, docs_path: Path) -> Dict[str, Any]:
        """分析目录结构"""
        analysis = {
            "total_files": 0,
            "total_dirs": 0,
            "file_types": {},
            "depth_distribution": {},
            "issues": [],
            "suggestions": []
        }
        
        # 遍历文档目录
        for item in docs_path.rglob("*"):
            if item.is_file():
                analysis["total_files"] += 1
                
                # 统计文件类型
                ext = item.suffix.lower()
                analysis["file_types"][ext] = analysis["file_types"].get(ext, 0) + 1
                
                # 统计目录深度
                depth = len(item.relative_to(docs_path).parts) - 1
                analysis["depth_distribution"][depth] = analysis["depth_distribution"].get(depth, 0) + 1
                
            elif item.is_dir():
                analysis["total_dirs"] += 1
        
        # 识别问题
        if analysis["total_dirs"] == 0 and analysis["total_files"] > 5:
            analysis["issues"].append("所有文件都在根目录，缺乏分类组织")
            analysis["suggestions"].append("建议按主题创建子目录，如: 'tutorials/', 'api-docs/', 'faq/'")
        
        if len(analysis["file_types"]) == 1:
            analysis["issues"].append(f"所有文档都是同一格式 ({list(analysis['file_types'].keys())[0]})")
            analysis["suggestions"].append("考虑使用 Markdown 格式以获得更好的可读性和结构化")
        
        # 检查是否有 README
        readme_exists = any(
            f.name.lower() in ['readme.md', 'readme.txt', 'index.md']
            for f in docs_path.iterdir() if f.is_file()
        )
        if not readme_exists:
            analysis["issues"].append("缺少 README 或索引文件")
            analysis["suggestions"].append("创建 README.md 作为知识库的入口和导航")
        
        return analysis
    
    def _analyze_content(self, docs_path: Path) -> Dict[str, Any]:
        """分析内容质量"""
        analysis = {
            "documents": [],
            "avg_length": 0,
            "issues": [],
            "suggestions": []
        }
        
        total_length = 0
        short_docs = []
        
        for file_path in docs_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in {'.txt', '.md'}:
                try:
                    content = file_path.read_text(encoding='utf-8')
                    length = len(content)
                    total_length += length
                    
                    doc_info = {
                        "name": file_path.name,
                        "path": str(file_path.relative_to(docs_path)),
                        "length": length,
                        "has_headings": '#' in content if file_path.suffix == '.md' else False,
                        "has_code_blocks": '```' in content
                    }
                    analysis["documents"].append(doc_info)
                    
                    if length < 200:
                        short_docs.append(file_path.name)
                        
                except Exception:
                    pass
        
        if analysis["documents"]:
            analysis["avg_length"] = total_length // len(analysis["documents"])
        
        if short_docs:
            analysis["issues"].append(f"以下文档内容过短: {', '.join(short_docs[:5])}")
            analysis["suggestions"].append("考虑合并相关的短文档或扩充内容")
        
        # 检查是否有文档缺少标题结构
        no_headings = [d["name"] for d in analysis["documents"] if not d["has_headings"]]
        if no_headings and len(no_headings) > len(analysis["documents"]) / 2:
            analysis["issues"].append("大部分 Markdown 文档缺少标题结构")
            analysis["suggestions"].append("使用 # 标题来组织文档结构，有助于 RAG 检索")
        
        return analysis
    
    def execute(self, **kwargs) -> ToolResult:
        """执行文档分析"""
        analysis_type = kwargs.get("analysis_type", "structure")
        
        try:
            docs_path = Path(self._documents_path)
            
            if not docs_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"文档目录不存在: {self._documents_path}"
                )
            
            results = {}
            output_parts = ["# 知识库文档分析报告\n"]
            
            if analysis_type in ["structure", "all"]:
                structure = self._analyze_structure(docs_path)
                results["structure"] = structure
                
                output_parts.append("## 📂 目录结构分析")
                output_parts.append(f"- 文件总数: {structure['total_files']}")
                output_parts.append(f"- 目录总数: {structure['total_dirs']}")
                output_parts.append(f"- 文件类型: {structure['file_types']}")
                
                if structure["issues"]:
                    output_parts.append("\n**发现的问题:**")
                    for issue in structure["issues"]:
                        output_parts.append(f"  ⚠️ {issue}")
                
                if structure["suggestions"]:
                    output_parts.append("\n**优化建议:**")
                    for sug in structure["suggestions"]:
                        output_parts.append(f"  💡 {sug}")
                output_parts.append("")
            
            if analysis_type in ["content", "all"]:
                content = self._analyze_content(docs_path)
                results["content"] = content
                
                output_parts.append("## 📝 内容质量分析")
                output_parts.append(f"- 文档数量: {len(content['documents'])}")
                output_parts.append(f"- 平均长度: {content['avg_length']} 字符")
                
                if content["issues"]:
                    output_parts.append("\n**发现的问题:**")
                    for issue in content["issues"]:
                        output_parts.append(f"  ⚠️ {issue}")
                
                if content["suggestions"]:
                    output_parts.append("\n**优化建议:**")
                    for sug in content["suggestions"]:
                        output_parts.append(f"  💡 {sug}")
            
            return ToolResult(
                success=True,
                output="\n".join(output_parts),
                data=results,
                metadata={"analysis_type": analysis_type}
            )
            
        except Exception as e:
            return ToolResult(success=False, output="", error=f"分析失败: {str(e)}")


class SummarizeTool(BaseTool):
    """文本总结工具"""
    
    def __init__(self):
        self._llm = None
        super().__init__()
    
    def _init_llm(self):
        """初始化 LLM"""
        if self._llm is None:
            if Config.MODEL_PROVIDER == "ollama":
                from langchain_community.llms import Ollama
                self._llm = Ollama(
                    base_url=Config.OLLAMA_API_URL,
                    model=Config.LLM_MODEL,
                    temperature=0.3,
                )
            else:
                from langchain.chat_models import init_chat_model
                self._llm = init_chat_model(
                    Config.LLM_MODEL,
                    temperature=0.3,
                )
        return self._llm
    
    @property
    def name(self) -> str:
        return "summarize"
    
    @property
    def description(self) -> str:
        return "总结长文本或多个文档的内容，生成简洁的摘要。"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "text",
                "type": "string",
                "description": "要总结的文本内容",
                "required": True
            },
            {
                "name": "style",
                "type": "string",
                "description": "总结风格: 'brief'(简短), 'detailed'(详细), 'bullet'(要点列表)，默认 'brief'",
                "required": False
            },
            {
                "name": "max_length",
                "type": "integer",
                "description": "摘要最大长度（字数），默认 200",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """执行文本总结"""
        text = kwargs.get("text", "")
        style = kwargs.get("style", "brief")
        max_length = kwargs.get("max_length", 200)
        
        if not text:
            return ToolResult(success=False, output="", error="文本内容不能为空")
        
        if len(text) < 100:
            return ToolResult(
                success=True,
                output=f"文本较短，无需总结:\n{text}",
                data={"summary": text, "original_length": len(text)}
            )
        
        try:
            llm = self._init_llm()
            
            style_instructions = {
                "brief": f"请用不超过{max_length}字总结以下内容，只保留最核心的信息：",
                "detailed": f"请详细总结以下内容，包含主要观点和关键细节（不超过{max_length * 2}字）：",
                "bullet": f"请用要点列表的形式总结以下内容的关键点（不超过{max_length}字）："
            }
            
            prompt = f"""{style_instructions.get(style, style_instructions['brief'])}

{text}

总结："""
            
            response = llm.invoke(prompt)
            summary = response if isinstance(response, str) else (
                response.content if hasattr(response, 'content') else str(response)
            )
            
            return ToolResult(
                success=True,
                output=f"**摘要** ({style} 风格):\n\n{summary.strip()}",
                data={
                    "summary": summary.strip(),
                    "original_length": len(text),
                    "summary_length": len(summary)
                },
                metadata={"style": style}
            )
            
        except Exception as e:
            return ToolResult(success=False, output="", error=f"总结失败: {str(e)}")


class GenerateReportTool(BaseTool):
    """生成报告工具"""
    
    def __init__(self):
        self._llm = None
        super().__init__()
    
    def _init_llm(self):
        if self._llm is None:
            if Config.MODEL_PROVIDER == "ollama":
                from langchain_community.llms import Ollama
                self._llm = Ollama(
                    base_url=Config.OLLAMA_API_URL,
                    model=Config.LLM_MODEL,
                    temperature=0.5,
                )
            else:
                from langchain.chat_models import init_chat_model
                self._llm = init_chat_model(Config.LLM_MODEL, temperature=0.5)
        return self._llm
    
    @property
    def name(self) -> str:
        return "generate_report"
    
    @property
    def description(self) -> str:
        return "根据收集的信息生成结构化报告，支持多种格式。"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "topic",
                "type": "string",
                "description": "报告主题",
                "required": True
            },
            {
                "name": "content",
                "type": "string",
                "description": "报告内容来源（可以是多段文本）",
                "required": True
            },
            {
                "name": "format",
                "type": "string",
                "description": "报告格式: 'markdown', 'plain', 'html'，默认 'markdown'",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """生成报告"""
        topic = kwargs.get("topic", "")
        content = kwargs.get("content", "")
        report_format = kwargs.get("format", "markdown")
        
        if not topic or not content:
            return ToolResult(success=False, output="", error="主题和内容不能为空")
        
        try:
            llm = self._init_llm()
            
            format_instructions = {
                "markdown": "使用 Markdown 格式，包含标题、列表、代码块等",
                "plain": "使用纯文本格式，结构清晰",
                "html": "使用 HTML 格式，包含适当的标签"
            }
            
            prompt = f"""请根据以下内容，生成一份关于"{topic}"的专业报告。

{format_instructions.get(report_format, format_instructions['markdown'])}

原始内容：
{content}

要求：
1. 包含摘要、正文、结论
2. 逻辑清晰，层次分明
3. 突出关键信息
4. 语言专业简洁

请生成报告："""
            
            response = llm.invoke(prompt)
            report = response if isinstance(response, str) else (
                response.content if hasattr(response, 'content') else str(response)
            )
            
            return ToolResult(
                success=True,
                output=report.strip(),
                data={
                    "topic": topic,
                    "report": report.strip(),
                    "format": report_format
                },
                metadata={"format": report_format}
            )
            
        except Exception as e:
            return ToolResult(success=False, output="", error=f"生成报告失败: {str(e)}")
