"""
因子组合服务 - StockQuant Pro
因子组合 CRUD，供双驱动回测与选股使用。
"""
from typing import Dict, List, Optional
from models.factor_combo import FactorCombo
from utils.database import db
import json


class FactorComboService:
    """因子组合服务类"""

    @staticmethod
    def _validate_factor_config(factor_config: dict) -> None:
        if not isinstance(factor_config, dict) or "factors" not in factor_config:
            raise ValueError("factor_config 必须包含 factors 数组")
        factors = factor_config.get("factors", [])
        if not isinstance(factors, list):
            raise ValueError("factor_config.factors 必须为数组")
        for f in factors:
            if not isinstance(f, dict) or "factor_code" not in f:
                raise ValueError("每个因子须包含 factor_code")

    @staticmethod
    def _normalize_factor_weights(factor_config: dict) -> dict:
        """对 factor_config.factors 做权重处理：若传 score（0-100 和=100）则转为 weight=score/100；否则缺 weight 则等权 1/n，权重和≠1 则归一化。返回新 dict，不修改入参。"""
        import copy
        config = copy.deepcopy(factor_config)
        factors = config.get("factors", [])
        if not factors:
            return config
        n = len(factors)
        # v2.3: 若存在 score 字段且有效，按总分 100 处理
        use_score = any(
            f.get("score") is not None and f.get("score") != ""
            for f in factors
        )
        if use_score:
            total_score = sum(float(f.get("score", 0) or 0) for f in factors)
            if total_score <= 0:
                for f in factors:
                    f["weight"] = 1.0 / n
            else:
                if abs(total_score - 100.0) > 0.01:
                    for f in factors:
                        f["weight"] = (float(f.get("score", 0) or 0) / total_score)
                else:
                    for f in factors:
                        f["weight"] = float(f.get("score", 0) or 0) / 100.0
            for f in factors:
                if f.get("direction") is None or f.get("direction") == "":
                    f["direction"] = "long"
            # 存储时只保留 weight，不持久化 score（前端可用 weight*100 展示）
            for f in factors:
                if "score" in f:
                    del f["score"]
            return config
        has_missing = any(
            f.get("weight") is None or (isinstance(f.get("weight"), (int, float)) and f.get("weight") == "")
            for f in factors
        )
        if has_missing:
            for f in factors:
                f["weight"] = 1.0 / n
                if f.get("direction") is None or f.get("direction") == "":
                    f["direction"] = "long"
        else:
            total = sum(float(f.get("weight", 0) or 0) for f in factors)
            if total <= 0:
                for f in factors:
                    f["weight"] = 1.0 / n
            elif abs(total - 1.0) > 0.01:
                for f in factors:
                    f["weight"] = float(f.get("weight", 0) or 0) / total
            for f in factors:
                if f.get("direction") is None or f.get("direction") == "":
                    f["direction"] = "long"
        return config

    @staticmethod
    def _validate_selection_rule(selection_rule: dict) -> None:
        if not isinstance(selection_rule, dict) or "type" not in selection_rule:
            raise ValueError("selection_rule 必须包含 type（topk 或 threshold）")
        t = selection_rule.get("type")
        if t == "topk" and "k" not in selection_rule:
            raise ValueError("selection_rule.type=topk 时须包含 k")
        if t == "threshold" and "field" not in selection_rule:
            raise ValueError("selection_rule.type=threshold 时须包含 field")

    @staticmethod
    def list(
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
    ) -> Dict:
        """分页列表"""
        query = FactorCombo.query
        if keyword:
            query = query.filter(FactorCombo.name.like(f"%{keyword}%"))
        total = query.count()
        offset = (page - 1) * page_size
        items = query.order_by(FactorCombo.updated_at.desc()).offset(offset).limit(page_size).all()
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [x.to_dict() for x in items],
        }

    @staticmethod
    def get_by_id(combo_id: int) -> Optional[Dict]:
        """单条详情"""
        combo = FactorCombo.query.get(combo_id)
        if combo is None:
            return None
        return combo.to_dict()

    @staticmethod
    def create(name: str, factor_config: dict, selection_rule: dict) -> Dict:
        """创建"""
        FactorComboService._validate_factor_config(factor_config)
        factor_config = FactorComboService._normalize_factor_weights(factor_config)
        FactorComboService._validate_selection_rule(selection_rule)
        combo = FactorCombo(
            name=name,
            factor_config=json.dumps(factor_config, ensure_ascii=False),
            selection_rule=json.dumps(selection_rule, ensure_ascii=False),
        )
        db.session.add(combo)
        db.session.commit()
        return combo.to_dict()

    @staticmethod
    def update(
        combo_id: int,
        name: Optional[str] = None,
        factor_config: Optional[dict] = None,
        selection_rule: Optional[dict] = None,
    ) -> Dict:
        """更新"""
        combo = FactorCombo.query.get(combo_id)
        if combo is None:
            raise ValueError("因子组合不存在")
        if name is not None:
            combo.name = name
        if factor_config is not None:
            FactorComboService._validate_factor_config(factor_config)
            factor_config = FactorComboService._normalize_factor_weights(factor_config)
            combo.factor_config = json.dumps(factor_config, ensure_ascii=False)
        if selection_rule is not None:
            FactorComboService._validate_selection_rule(selection_rule)
            combo.selection_rule = json.dumps(selection_rule, ensure_ascii=False)
        db.session.commit()
        return combo.to_dict()

    @staticmethod
    def delete(combo_id: int) -> bool:
        """删除"""
        combo = FactorCombo.query.get(combo_id)
        if combo is None:
            return False
        db.session.delete(combo)
        db.session.commit()
        return True
