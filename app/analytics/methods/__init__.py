"""分析方法子包 — 自动导入所有已注册方法"""

# 导入各方法模块，触发 @register_method 装饰器注册
from app.analytics.methods import descriptive  # noqa: F401
from app.analytics.methods import spc  # noqa: F401
from app.analytics.methods import hypothesis  # noqa: F401
from app.analytics.methods import correlation  # noqa: F401
from app.analytics.methods import pareto  # noqa: F401
from app.analytics.methods import regression  # noqa: F401
from app.analytics.methods import prediction  # noqa: F401
from app.analytics.methods import anomaly  # noqa: F401
