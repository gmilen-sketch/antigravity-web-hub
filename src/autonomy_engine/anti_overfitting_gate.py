import math
from typing import Dict, Any, Tuple

class AntiOverfittingGate:
    def __init__(self, min_d_prime: float = 1.80, max_abs_c: float = 0.35, max_token_growth_pct: float = 10.0, max_semantic_drift: float = 0.15):
        self.min_d_prime = min_d_prime
        self.max_abs_c = max_abs_c
        self.max_token_growth_pct = max_token_growth_pct
        self.max_semantic_drift = max_semantic_drift

    @staticmethod
    def _inv_norm_cdf(p: float) -> float:
        # Acklam rational approximation algorithm for standard normal quantile function
        a = [-3.969683028665376e+01,  2.209460984245205e+02,
             -2.759285104469687e+02,  1.383577518672690e+02,
             -3.066479806614716e+01,  2.506628277459239e+00]
        b = [-5.447609879822406e+01,  1.615858368580409e+02,
             -1.556989798598866e+02,  6.680131188771972e+01,
             -1.328068155288572e+01]
        c = [-7.784894002430293e-03, -3.223964580411365e-01,
             -2.400758277161838e+00, -2.549732539343734e+00,
              4.374664141464968e+00,  2.938163982698783e+00]
        d = [ 7.784695709041462e-03,  3.224671290700398e-01,
              2.445134137142996e+00,  3.754408661907416e+00]

        p = max(1e-7, min(1.0 - 1e-7, p))
        p_low = 0.02425
        p_high = 1.0 - p_low

        if p < p_low:
            q = math.sqrt(-2 * math.log(p))
            return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) /                    ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1.0)
        elif p <= p_high:
            q = p - 0.5
            r = q * q
            return q * (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) /                        (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1.0)
        else:
            q = math.sqrt(-2 * math.log(1.0 - p))
            return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) /                     ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1.0)

    def compute_sdt_metrics(self, hits: int, total_positives: int, false_alarms: int, total_negatives: int) -> Tuple[float, float]:
        hit_rate = max(0.001, min(0.999, hits / max(total_positives, 1)))
        fa_rate = max(0.001, min(0.999, false_alarms / max(total_negatives, 1)))
        z_hit = self._inv_norm_cdf(hit_rate)
        z_fa = self._inv_norm_cdf(fa_rate)
        d_prime = z_hit - z_fa
        c_bias = -0.5 * (z_hit + z_fa)
        return d_prime, c_bias

    def evaluate_patch(self, hits: int, total_positives: int, false_alarms: int, total_negatives: int, orig_token_len: int, new_token_len: int, semantic_drift: float = 0.05) -> Dict[str, Any]:
        d_prime, c_bias = self.compute_sdt_metrics(hits, total_positives, false_alarms, total_negatives)
        growth_pct = ((new_token_len - orig_token_len) / max(orig_token_len, 1)) * 100.0
        passes_sdt = (d_prime >= self.min_d_prime) and (abs(c_bias) <= self.max_abs_c)
        passes_epc = (growth_pct <= self.max_token_growth_pct) and (semantic_drift <= self.max_semantic_drift)
        approved = passes_sdt and passes_epc
        return {
            "approved": approved,
            "d_prime": round(d_prime, 4),
            "c_bias": round(c_bias, 4),
            "growth_pct": round(growth_pct, 2),
            "semantic_drift": round(semantic_drift, 4),
            "passes_sdt": passes_sdt,
            "passes_epc": passes_epc
        }
