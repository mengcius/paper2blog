"""
Prompt management system for paper2slides.

This module provides a PromptManager class that handles loading and rendering
of prompt templates from YAML configuration files.
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)


class PromptManager:
    """
    Manages prompt templates and renders them with variables.

    The PromptManager loads prompts from a YAML configuration file and provides
    methods to render them with specific variables for different stages of the
    slide generation process.
    """

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize the PromptManager.

        Args:
            config_path: Path to the YAML configuration file. If None, uses
                        the default config.yaml in the prompts directory.
        """
        if config_path is None:
            # Default to config.yaml in the same directory as this file
            # Use pathlib for cross-platform path handling
            config_path = Path(__file__).parent / "config.yaml"

        # Ensure we have a Path object for consistent handling
        self.config_path = Path(config_path).resolve()
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        Load the YAML configuration file.

        Returns:
            Dict containing the loaded configuration.

        Raises:
            FileNotFoundError: If the config file doesn't exist.
            yaml.YAMLError: If the config file is malformed.
        """
        try:
            # Use pathlib's open method for cross-platform compatibility
            with self.config_path.open("r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded prompt configuration from {self.config_path}")
                return config
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Prompt configuration file not found: {self.config_path}"
            )
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Error parsing YAML configuration: {e}")

    def get_system_message(self, stage_name: str) -> str:
        """
        Get the system message for a specific stage.

        Args:
            stage_name: Name of the stage ('initial', 'update', or 'revise').

        Returns:
            The system message string for the specified stage.

        Raises:
            KeyError: If the stage_name is not found in the configuration.
        """
        try:
            return self.config["stages"][stage_name]["system"]
        except KeyError:
            available_stages = list(self.config["stages"].keys())
            raise KeyError(
                f"Stage '{stage_name}' not found. Available stages: {available_stages}"
            )

    def get_prompt(self, stage_name: str, **kwargs) -> str:
        """
        Get and render a prompt template for a specific stage.

        Args:
            stage_name: Name of the stage ('initial', 'update', or 'revise').
            **kwargs: Variables to substitute in the template.

        Returns:
            The rendered prompt string with variables substituted.

        Raises:
            KeyError: If the stage_name is not found or required variables are missing.
        """
        try:
            # Merge defaults with provided kwargs
            context = {**self.config.get("defaults", {}), **kwargs}

            # Get the template
            template = self.config["stages"][stage_name]["template"]

            # Render the template
            rendered = template.format(**context)

            logger.debug(
                f"Rendered prompt for stage '{stage_name}' with {len(context)} variables"
            )
            return rendered

        except KeyError as e:
            if stage_name not in self.config["stages"]:
                available_stages = list(self.config["stages"].keys())
                raise KeyError(
                    f"Stage '{stage_name}' not found. Available stages: {available_stages}"
                )
            else:
                # Missing variable in template
                raise KeyError(f"Missing required variable for template rendering: {e}")
        except Exception as e:
            raise ValueError(f"Error rendering prompt for stage '{stage_name}': {e}")

    def validate_variables(self, stage_name: str, **kwargs) -> bool:
        """
        Validate that all required variables are provided for a stage.

        Args:
            stage_name: Name of the stage to validate.
            **kwargs: Variables to check.

        Returns:
            True if all required variables are provided.

        Raises:
            ValueError: If required variables are missing.
        """
        try:
            template = self.config["stages"][stage_name]["template"]

            # Extract required variables from template
            import string

            formatter = string.Formatter()
            required_vars = []

            for _, field_name, _, _ in formatter.parse(template):
                if field_name is not None and field_name not in required_vars:
                    required_vars.append(field_name)

            # Check which variables are available (defaults + provided)
            available_vars = set(self.config.get("defaults", {}).keys()) | set(
                kwargs.keys()
            )
            missing_vars = set(required_vars) - available_vars

            if missing_vars:
                raise ValueError(
                    f"Missing required variables for stage '{stage_name}': {missing_vars}"
                )

            return True

        except KeyError:
            available_stages = list(self.config["stages"].keys())
            raise KeyError(
                f"Stage '{stage_name}' not found. Available stages: {available_stages}"
            )

    def list_stages(self) -> list:
        """
        Get a list of available stage names.

        Returns:
            List of stage names available in the configuration.
        """
        return list(self.config["stages"].keys())

    def get_defaults(self) -> Dict[str, Any]:
        """
        Get the default variables from the configuration.

        Returns:
            Dict containing default variables.
        """
        return self.config.get("defaults", {})

    def reload_config(self) -> None:
        """
        Reload the configuration from the file.

        This is useful if the configuration file has been modified and you
        want to pick up the changes without recreating the PromptManager.
        """
        self.config = self._load_config()
        logger.info("Prompt configuration reloaded")

    # New helper to assemble prompts consistently across stages
    def build_prompt(
        self,
        stage: int | str,
        latex_source: str,
        beamer_code: str = "",
        linter_log: str = "",
        figure_paths: list[str] | None = None,
    ) -> tuple[str, str]:
        """
        Build (system_message, rendered_prompt) for the given stage.
        Supports stage as 1/2/3 or 'initial'/'update'/'revise'.
        """
        if isinstance(stage, int):
            stage_map = {1: "initial", 2: "update", 3: "revise"}
            if stage not in stage_map:
                raise ValueError(
                    "Invalid stage. Use 1, 2, 3 or 'initial'/'update'/'revise'."
                )
            stage_name = stage_map[stage]
        else:
            stage_name = stage

        # Assemble variables expected by templates
        vars: Dict[str, Any] = {
            "latex_source": latex_source,
            "figure_paths": " ".join(figure_paths or []),
        }
        if stage_name in ("update", "revise"):
            vars["beamer_code"] = beamer_code
        if stage_name == "revise":
            vars["linter_log"] = linter_log

        system_message = self.get_system_message(stage_name)
        user_prompt = self.get_prompt(stage_name, **vars)
        return system_message, user_prompt

    def build_blog_prompt(
        self,
        latex_source: str,
        image_paths: list[str] | None = None,
        language: str = "en",
    ) -> tuple[str, str]:
        """
        Build (system_message, rendered_prompt) for blog post generation.
        
        Args:
            latex_source: The LaTeX source of the paper
            image_paths: List of image paths
            language: Language for the blog post ("en" for English, "zh" for Chinese)
        """
        # Determine which stage to use based on language
        stage_name = "blog_zh" if language == "zh" else "blog"
        
        # Add blog-specific stage to config if not exists
        if stage_name not in self.config["stages"]:
            # Define default blog prompts
            if language == "zh":
                blog_system = "你是一位专业的科学 writer，专门将学术论文翻译成中文博客文章，适合微信公众号等中文平台发布。你的读者主要是对AI/机器学习感兴趣的技术专业人士和研究人员。"
                blog_template = """
请仔细阅读这篇学术论文，并创建一篇适合微信公众号风格的中文Markdown博客文章。目标读者是对AI/机器学习感兴趣的技术专业人士和研究人员。确保博客文章内容完整且易于理解。请遵循以下指导原则：

- 结构：按照论文的逻辑顺序组织博客文章：
  - 标题：使用论文的完整标题作为博客标题
  - 作者信息：包含第一作者的姓名和所属机构（如果可用）
  - 引言：简要说明论文的内容及其重要性
  - 主要内容：详细解释关键概念、方法和发现
  - 结果：重点介绍最重要的实验结果和定量数据
  - 结论：总结工作的贡献和意义
  - 参考文献：列出关键参考文献（可以用[1]、[2]等方式引用）

- 风格：
  - 使用清晰易懂的语言，避免过多的专业术语
  - 使用要点列表和短段落以提高可读性
  - 包含章节标题来组织内容
  - 适当使用粗体文字强调关键点
  - 谨慎使用表情符号来增强吸引力（例如，🔍 表示见解，📊 表示结果）

- 图片：
  - 包含相关图表来说明关键概念
  - 将图片放置在引用它们的文本附近
  - 为每张图片添加描述性标题
  - 以下是你可以使用的图片路径列表：
  {image_paths}
  
  在Markdown中插入图片请使用以下格式：
  ![标题](图片路径)
  
  注意所有PDF图片已转换为PNG格式以获得更好的网页兼容性。

- 数学公式：
  - 对于简单公式，使用行内数学符号如 $E = mc^2$
  - 对于复杂公式，使用块级数学符号：
    $$
    E = mc^2
    $$
  - 始终用通俗语言解释数学符号和概念

论文内容：
{latex_source}

现在请提供完整的中文Markdown博客文章：以`````开头，提供内容，然后以````结尾。提供完整的博客文章。
"""
            else:
                blog_system = "You are a professional science writer who specializes in translating academic papers into engaging blog posts for a general technical audience."
                blog_template = """
Please read this academic paper and create a WeChat-style Markdown blog post. The intended audience includes technical professionals and researchers interested in AI/machine learning. Ensure the blog post is self-contained and understandable independently. Pay attention to the following guidelines:

- Structure: Organize the blog post in a logical sequence, typically following the structure of the paper:
  - Title: Use the full paper title as the blog title
  - Author information: Include the first author's name and affiliation if available
  - Introduction: Briefly explain what the paper is about and why it matters
  - Main content: Explain the key ideas, methods, and findings in detail
  - Results: Highlight the most important experimental results with quantitative data
  - Conclusion: Summarize the contributions and implications of the work
  - References: List key references (you can cite them as [1], [2], etc.)

- Style:
  - Write in clear, accessible language avoiding excessive jargon
  - Use bullet points and short paragraphs for readability
  - Include section headings to organize content
  - Emphasize key points with bold text where appropriate
  - Use emojis sparingly to enhance engagement (e.g., 🔍 for insights, 📊 for results)

- Images:
  - Include relevant figures and diagrams to illustrate key concepts
  - Place images close to the text that references them
  - Add descriptive captions for each image
  - Here is the list of image paths that you are allowed to use:
  {image_paths}
  
  To include an image in Markdown, use the following format:
  ![Caption](image_path)

- Math:
  - For simple equations, use inline math notation like $E = mc^2$
  - For complex equations, use block math notation:
    $$
    E = mc^2
    $$
  - Always explain mathematical notation and concepts in plain language

Paper content:
{latex_source}

Now provide the complete Markdown blog post: start with ``````, provide the content, and then end with ```. Provide the full blog post at once.
"""
            # Temporarily add to config
            self.config["stages"][stage_name] = {
                "system": blog_system,
                "template": blog_template
            }

        # Assemble variables expected by templates
        vars: Dict[str, Any] = {
            "latex_source": latex_source,
            "image_paths": "\n".join(image_paths or []),
        }

        system_message = self.get_system_message(stage_name)
        user_prompt = self.get_prompt(stage_name, **vars)
        return system_message, user_prompt


# Convenience function for backward compatibility
def get_prompt_manager(config_path: Optional[Union[str, Path]] = None) -> PromptManager:
    """
    Factory function to create a PromptManager instance.

    Args:
        config_path: Optional path to configuration file.

    Returns:
        PromptManager instance.
    """
    return PromptManager(config_path)
