"""
Data Agent: 数据是否可用
Real implementation with:
- Data source validation
- Schema detection
- PII scanning
- Data quality checks
- Retrieval integration
"""
from runtime.agents.base_agent import BaseAgent
from typing import Dict, Any, List, Optional, Tuple
import os
import json
import hashlib
import re
from datetime import datetime
from runtime.llm import get_llm_adapter
from runtime.llm.prompt_loader import PromptLoader


class DataValidationResult:
    """Result of data validation"""
    def __init__(
        self,
        valid: bool,
        source: str,
        data_hash: str,
        pii_detected: bool = False,
        pii_types: List[str] = None,
        schema_detected: Dict[str, Any] = None,
        quality_score: float = 1.0,
        issues: List[str] = None,
        warnings: List[str] = None
    ):
        self.valid = valid
        self.source = source
        self.data_hash = data_hash
        self.pii_detected = pii_detected
        self.pii_types = pii_types or []
        self.schema_detected = schema_detected or {}
        self.quality_score = quality_score
        self.issues = issues or []
        self.warnings = warnings or []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "source": self.source,
            "data_hash": self.data_hash,
            "pii_detected": self.pii_detected,
            "pii_types": self.pii_types,
            "schema_detected": self.schema_detected,
            "quality_score": self.quality_score,
            "issues": self.issues,
            "warnings": self.warnings
        }


class PIIScanner:
    """Scans for Personally Identifiable Information"""
    
    # PII patterns (regex-based)
    PATTERNS = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone_cn": r'\b1[3-9]\d{9}\b',
        "phone_intl": r'\b\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b',
        "id_card_cn": r'\b\d{17}[\dXx]\b',
        "ssn_us": r'\b\d{3}-\d{2}-\d{4}\b',
        "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        "ip_address": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        "passport": r'\b[A-Z]{1,2}\d{6,9}\b',
    }
    
    @classmethod
    def scan(cls, text: str) -> Tuple[bool, List[str]]:
        """
        Scan text for PII.
        
        Returns:
            Tuple of (pii_detected, list_of_pii_types)
        """
        detected_types = []
        
        for pii_type, pattern in cls.PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                detected_types.append(pii_type)
        
        return len(detected_types) > 0, detected_types


class DataQualityChecker:
    """Checks data quality metrics"""
    
    @classmethod
    def check(cls, data: Any) -> Tuple[float, List[str], List[str]]:
        """
        Check data quality.
        
        Returns:
            Tuple of (quality_score, issues, warnings)
        """
        issues = []
        warnings = []
        score = 1.0
        
        if data is None:
            return 0.0, ["Data is None"], []
        
        # Check for empty data
        if isinstance(data, str):
            if len(data.strip()) == 0:
                return 0.0, ["Data is empty"], []
            if len(data) < 10:
                warnings.append("Data is very short")
                score -= 0.1
        
        elif isinstance(data, dict):
            if len(data) == 0:
                return 0.0, ["Dictionary is empty"], []
            
            # Check for null values
            null_count = sum(1 for v in data.values() if v is None)
            if null_count > 0:
                warnings.append(f"{null_count} null values found")
                score -= 0.05 * null_count
        
        elif isinstance(data, list):
            if len(data) == 0:
                return 0.0, ["List is empty"], []
            
            # Check for duplicates
            try:
                unique_count = len(set(str(item) for item in data))
                if unique_count < len(data) * 0.5:
                    warnings.append("High duplicate rate detected")
                    score -= 0.2
            except Exception:
                pass
        
        return max(0.0, min(1.0, score)), issues, warnings


class DataAgent(BaseAgent):
    """
    Real Data Agent implementation.
    
    Responsibilities:
    - Validate data sources
    - Detect schemas
    - Scan for PII
    - Check data quality
    - Integrate with retrieval layer
    """
    
    def __init__(self):
        super().__init__("Data")
        self.llm_adapter = get_llm_adapter()
        self.prompt_loader = PromptLoader()
        self.pii_scanner = PIIScanner()
        self.quality_checker = DataQualityChecker()
    
    async def execute(self, context: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """
        Execute data validation and preparation.
        
        Workflow:
        1. Extract data sources from spec
        2. Validate each source
        3. Scan for PII
        4. Check data quality
        5. Prepare data manifest
        6. Optionally ingest into vector store
        """
        spec = context.get("spec", {})
        data_sources = spec.get("data_sources", [])
        
        # Initialize results
        validation_results: List[DataValidationResult] = []
        all_valid = True
        total_pii_detected = False
        pii_types_found: List[str] = []
        all_issues: List[str] = []
        all_warnings: List[str] = []
        
        # If no data sources specified, create a default validation
        if not data_sources:
            # Check if there's inline data in the spec
            inline_data = spec.get("data") or spec.get("content") or spec.get("documents")
            
            if inline_data:
                result = await self._validate_inline_data(inline_data, task_id)
                validation_results.append(result)
                all_valid = result.valid
                total_pii_detected = result.pii_detected
                pii_types_found.extend(result.pii_types)
                all_issues.extend(result.issues)
                all_warnings.extend(result.warnings)
            else:
                # No data sources and no inline data - still valid but with warning
                all_warnings.append("No data sources specified in spec")
        else:
            # Validate each data source
            for source in data_sources:
                result = await self._validate_source(source, task_id)
                validation_results.append(result)
                
                if not result.valid:
                    all_valid = False
                    all_issues.extend(result.issues)
                
                if result.pii_detected:
                    total_pii_detected = True
                    pii_types_found.extend(result.pii_types)
                
                all_warnings.extend(result.warnings)
        
        # Calculate overall quality score
        if validation_results:
            avg_quality = sum(r.quality_score for r in validation_results) / len(validation_results)
        else:
            avg_quality = 0.8  # Default for empty sources
        
        # Determine decision
        if not all_valid:
            decision = "data_invalid"
            reason = f"数据验证失败: {'; '.join(all_issues[:3])}"
        elif total_pii_detected:
            decision = "data_pii_warning"
            reason = f"检测到 PII 数据类型: {', '.join(set(pii_types_found))}"
        else:
            decision = "data_ready"
            reason = f"数据验证通过 (质量分: {avg_quality:.2f})"
        
        # Add warnings to reason if any
        if all_warnings:
            reason += f" 警告: {'; '.join(all_warnings[:3])}"
        
        # Call LLM for additional analysis (optional)
        llm_analysis = None
        llm_meta = {"llm_used": False}
        
        if validation_results:
            try:
                llm_analysis, llm_meta = await self._call_llm_for_analysis(
                    validation_results, task_id, context.get("tenant_id", "default")
                )
            except Exception:
                pass
        
        # Build data manifest
        data_manifest = {
            "sources_count": len(validation_results),
            "all_valid": all_valid,
            "pii_detected": total_pii_detected,
            "pii_types": list(set(pii_types_found)),
            "quality_score": avg_quality,
            "issues": all_issues,
            "warnings": all_warnings,
            "validation_details": [r.to_dict() for r in validation_results],
            "validated_at": datetime.now().isoformat()
        }
        
        # Save data manifest artifact
        self._save_data_manifest(task_id, data_manifest)
        
        return {
            "decision": decision,
            "reason": reason,
            "data_manifest": data_manifest,
            "llm_result": llm_meta,
            "llm_analysis": llm_analysis,
            "state_update": {
                "data_agent_executed": True,
                "data_manifest": {
                    "sources_count": len(validation_results),
                    "quality_score": avg_quality,
                    "pii_detected": total_pii_detected,
                    "all_valid": all_valid
                },
                "data_ready": all_valid,
                "pii_warning": total_pii_detected
            }
        }
    
    async def _validate_source(
        self,
        source: Any,
        task_id: str
    ) -> DataValidationResult:
        """Validate a single data source"""
        issues = []
        warnings = []
        
        # Handle different source types
        if isinstance(source, str):
            # Could be a file path or URL
            if os.path.exists(source):
                return await self._validate_file_source(source, task_id)
            elif source.startswith(("http://", "https://")):
                return await self._validate_url_source(source, task_id)
            else:
                # Treat as inline text
                return await self._validate_inline_data(source, task_id)
        
        elif isinstance(source, dict):
            # Could be structured source definition
            source_type = source.get("type", "unknown")
            source_path = source.get("path") or source.get("url") or source.get("data")
            
            if source_type == "file" and source_path:
                return await self._validate_file_source(source_path, task_id)
            elif source_type == "url" and source_path:
                return await self._validate_url_source(source_path, task_id)
            elif source_type == "inline" or "data" in source:
                return await self._validate_inline_data(source.get("data", source), task_id)
            else:
                issues.append(f"Unknown source type: {source_type}")
        
        # Unknown source format
        issues.append("Unable to parse data source")
        return DataValidationResult(
            valid=False,
            source=str(source)[:100],
            data_hash="",
            issues=issues
        )
    
    async def _validate_file_source(
        self,
        path: str,
        task_id: str
    ) -> DataValidationResult:
        """Validate a file data source"""
        issues = []
        warnings = []
        
        if not os.path.exists(path):
            return DataValidationResult(
                valid=False,
                source=path,
                data_hash="",
                issues=[f"File not found: {path}"]
            )
        
        try:
            # Read file content
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Calculate hash
            data_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
            
            # Detect schema
            schema = self._detect_schema(content, path)
            
            # Scan for PII
            pii_detected, pii_types = self.pii_scanner.scan(content)
            
            # Check quality
            quality_score, qual_issues, qual_warnings = self.quality_checker.check(content)
            issues.extend(qual_issues)
            warnings.extend(qual_warnings)
            
            return DataValidationResult(
                valid=len(issues) == 0,
                source=path,
                data_hash=data_hash,
                pii_detected=pii_detected,
                pii_types=pii_types,
                schema_detected=schema,
                quality_score=quality_score,
                issues=issues,
                warnings=warnings
            )
        
        except Exception as e:
            return DataValidationResult(
                valid=False,
                source=path,
                data_hash="",
                issues=[f"Error reading file: {str(e)}"]
            )
    
    async def _validate_url_source(
        self,
        url: str,
        task_id: str
    ) -> DataValidationResult:
        """Validate a URL data source"""
        # For now, just validate URL format
        # In production: actually fetch and validate content
        
        import re
        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE
        )
        
        if url_pattern.match(url):
            return DataValidationResult(
                valid=True,
                source=url,
                data_hash=hashlib.sha256(url.encode()).hexdigest()[:16],
                warnings=["URL source not fetched - validation deferred"]
            )
        else:
            return DataValidationResult(
                valid=False,
                source=url,
                data_hash="",
                issues=["Invalid URL format"]
            )
    
    async def _validate_inline_data(
        self,
        data: Any,
        task_id: str
    ) -> DataValidationResult:
        """Validate inline data"""
        # Convert to string for analysis
        if isinstance(data, dict) or isinstance(data, list):
            content = json.dumps(data, ensure_ascii=False)
        else:
            content = str(data)
        
        # Calculate hash
        data_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        # Detect schema
        schema = self._detect_schema(content, "inline")
        
        # Scan for PII
        pii_detected, pii_types = self.pii_scanner.scan(content)
        
        # Check quality
        quality_score, issues, warnings = self.quality_checker.check(data)
        
        return DataValidationResult(
            valid=len(issues) == 0,
            source="inline",
            data_hash=data_hash,
            pii_detected=pii_detected,
            pii_types=pii_types,
            schema_detected=schema,
            quality_score=quality_score,
            issues=issues,
            warnings=warnings
        )
    
    def _detect_schema(self, content: str, source: str) -> Dict[str, Any]:
        """Detect data schema"""
        schema = {"type": "unknown", "format": "unknown"}
        
        # Try JSON
        try:
            data = json.loads(content)
            schema["type"] = "json"
            if isinstance(data, dict):
                schema["format"] = "object"
                schema["keys"] = list(data.keys())[:10]
            elif isinstance(data, list):
                schema["format"] = "array"
                schema["length"] = len(data)
            return schema
        except json.JSONDecodeError:
            pass
        
        # Check file extension
        if "." in source:
            ext = source.rsplit(".", 1)[-1].lower()
            if ext in ["csv", "tsv"]:
                schema["type"] = "csv"
                schema["format"] = "tabular"
            elif ext in ["txt", "md", "markdown"]:
                schema["type"] = "text"
                schema["format"] = "plain"
            elif ext in ["pdf"]:
                schema["type"] = "pdf"
                schema["format"] = "document"
            elif ext in ["yaml", "yml"]:
                schema["type"] = "yaml"
                schema["format"] = "structured"
        
        # Default to text
        if schema["type"] == "unknown":
            schema["type"] = "text"
            schema["format"] = "plain"
            schema["length"] = len(content)
        
        return schema
    
    async def _call_llm_for_analysis(
        self,
        results: List[DataValidationResult],
        task_id: str,
        tenant_id: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Call LLM for additional data analysis"""
        try:
            prompt_data = self.prompt_loader.load_prompt("data", "analyzer", "v1")
        except Exception:
            # Fallback if prompt not found
            return {}, {"llm_used": False}
        
        # Build summary of validation results
        summary = json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False)
        
        user_prompt = prompt_data.get("user_prompt_template", "Analyze: {summary}").format(
            summary=summary[:2000]  # Truncate for token limits
        )
        
        result, meta = await self.llm_adapter.call(
            system_prompt=prompt_data.get("system_prompt", "You are a data quality analyst."),
            user_prompt=user_prompt,
            schema=prompt_data.get("json_schema", {}),
            meta={"prompt_version": prompt_data.get("version", "1.0")},
            task_id=task_id,
            tenant_id=tenant_id
        )
        
        return result, meta
    
    def _save_data_manifest(self, task_id: str, manifest: Dict[str, Any]):
        """Save data manifest artifact"""
        artifact_dir = os.path.join("artifacts", "rag_project", task_id)
        os.makedirs(artifact_dir, exist_ok=True)
        
        manifest_path = os.path.join(artifact_dir, "data_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    def get_governing_question(self) -> str:
        return "数据是否可用？是否合规？质量是否达标？"
