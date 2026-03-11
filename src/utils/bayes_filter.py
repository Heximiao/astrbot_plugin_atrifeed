import math
import os
import jieba

class AtriBayesFilter:
    def __init__(self, data_dir: str):
        self.normal_words = {}
        self.abuse_words = {}
        self.total_normal = 0
        self.total_abuse = 0
        self.vocab = set()
        self.load_data(data_dir)

    def load_data(self, data_dir):
        """加载语料并统计词频"""
        normal_path = os.path.join(data_dir, "normal.txt")
        abuse_path = os.path.join(data_dir, "abuse.txt")

        if not os.path.exists(normal_path) or not os.path.exists(abuse_path):
            # 如果文件不存在，默认给一点基础数据防止报错
            self.total_normal, self.total_abuse = 1, 1
            return

        with open(normal_path, 'r', encoding='utf-8') as f:
            for line in f:
                self.total_normal += 1
                words = jieba.lcut(line.strip().lower())
                for w in words:
                    self.normal_words[w] = self.normal_words.get(w, 0) + 1
                    self.vocab.add(w)

        with open(abuse_path, 'r', encoding='utf-8') as f:
            for line in f:
                self.total_abuse += 1
                words = jieba.lcut(line.strip().lower())
                for w in words:
                    self.abuse_words[w] = self.abuse_words.get(w, 0) + 1
                    self.vocab.add(w)

    def is_abuse(self, text: str, threshold: float = 0.7) -> bool:
        """判断是否为辱骂。threshold 越高越不容易误判"""
        words = jieba.lcut(text.lower())

        target_text = text.strip().lower()
        
        # 如果这个句子在辱骂库里原封不动出现过，直接返回 True (相当于概率 1.0)
        # 注意：这里需要我们在 load_data 时顺便存一份原始句子列表
        if target_text in self.raw_abuse_lines:
            return True
        
        # P(Abuse|Text) 
        log_p_normal = math.log(self.total_normal / (self.total_normal + self.total_abuse))
        log_p_abuse = math.log(self.total_abuse / (self.total_normal + self.total_abuse))

        for w in words:
            # 拉普拉斯平滑
            p_w_normal = (self.normal_words.get(w, 0) + 1) / (len(self.vocab) + sum(self.normal_words.values()))
            p_w_abuse = (self.abuse_words.get(w, 0) + 1) / (len(self.vocab) + sum(self.abuse_words.values()))
            
            log_p_normal += math.log(p_w_normal)
            log_p_abuse += math.log(p_w_abuse)

        # 转化为概率（简化处理）
        try:
            prob_abuse = 1 / (1 + math.exp(min(700, max(-700, log_p_normal - log_p_abuse))))
        except:
            prob_abuse = 0.5
        return prob_abuse > threshold
    
    def get_debug_info(self, text: str):
        """详细拆解计算过程"""
        words = jieba.lcut(text.lower())
        
        # 基础得分（先验概率）
        total_samples = max(1, self.total_normal + self.total_abuse)
        base_normal_score = math.log(max(1, self.total_normal) / total_samples)
        base_abuse_score = math.log(max(1, self.total_abuse) / total_samples)
        
        word_details = []
        log_p_normal = base_normal_score
        log_p_abuse = base_abuse_score

        # 保底分母
        denom_normal = max(1, len(self.vocab) + sum(self.normal_words.values()))
        denom_abuse = max(1, len(self.vocab) + sum(self.abuse_words.values()))

        for w in words:
            # 计算单个词的概率
            p_w_normal = (self.normal_words.get(w, 0) + 1) / denom_normal
            p_w_abuse = (self.abuse_words.get(w, 0) + 1) / denom_abuse
            
            # 词分值贡献（分值越高代表越倾向于那一类）
            w_normal_log = math.log(p_w_normal)
            w_abuse_log = math.log(p_w_abuse)
            
            log_p_normal += w_normal_log
            log_p_abuse += w_abuse_log
            
            word_details.append({
                "词": w,
                "正常分贡献": f"{w_normal_log:.2f}",
                "辱骂分贡献": f"{w_abuse_log:.2f}",
                "倾向": "🔴辱骂" if w_abuse_log > w_normal_log else "🟢正常"
            })

        # 最终概率转换
        try:
            prob_abuse = 1 / (1 + math.exp(min(700, max(-700, log_p_normal - log_p_abuse))))
        except:
            prob_abuse = 0.5
            
        return {
            "words": word_details,
            "total_prob": prob_abuse,
            "final_decision": "辱骂" if prob_abuse > 0.7 else "正常"
        }