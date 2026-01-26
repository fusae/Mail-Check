#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI舆情分析模块
使用智谱AI判断舆情是否为负面
"""

import json
import logging
import re
import sqlite3

import requests
import yaml

class SentimentAnalyzer:
    def __init__(self, config):
        self.ai_config = config['ai']
        self.provider = self.ai_config['provider']
        self.model = self.ai_config['model']
        self.api_key = self.ai_config['api_key']
        self.api_url = self.ai_config['api_url']
        self.temperature = self.ai_config.get('temperature', 0.3)
        self.max_tokens = self.ai_config.get('max_tokens', 500)

        self.runtime_config = config.get('runtime', {})
        self.feedback_config = config.get('feedback', {})
        self.db_path = self.runtime_config.get('database_path')
        
        self.logger = logging.getLogger(__name__)
    
    def analyze(self, sentiment, hospital_name):
        """分析舆情是否为负面"""
        rule_result = self._apply_feedback_rules(sentiment)
        if rule_result:
            return rule_result

        if self.provider == 'zhipu':
            return self._analyze_with_zhipu(sentiment, hospital_name)
        else:
            self.logger.warning(f"不支持的AI提供商: {self.provider}")
            return self._default_analysis(sentiment)
    
    def _analyze_with_zhipu(self, sentiment, hospital_name):
        """使用智谱AI分析"""
        try:
            # 构建提示词
            prompt = self._build_prompt(sentiment, hospital_name)
            
            # 构建请求
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的舆情分析助手。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
            
            # 发送请求
            self.logger.info(f"调用智谱AI分析舆情...")
            response = requests.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            
            # 解析响应
            content = result['choices'][0]['message']['content']
            self.logger.info(f"AI返回: {content}")
            
            # 尝试解析JSON
            try:
                analysis = json.loads(content)
                
                # 验证返回格式
                if 'is_negative' not in analysis:
                    self.logger.warning("AI返回格式不正确")
                    return self._default_analysis(sentiment)
                
                return {
                    'is_negative': analysis.get('is_negative', False),
                    'actual_hospital': analysis.get('actual_hospital', None),
                    'reason': analysis.get('reason', '未提供理由'),
                    'severity': analysis.get('severity', 'medium'),
                    'confidence': 'high'
                }
            except json.JSONDecodeError:
                # 如果无法解析JSON，尝试简单判断
                self.logger.warning("无法解析AI返回的JSON")
                
                if '是负面' in content or 'true' in content.lower():
                    return {
                        'is_negative': True,
                        'actual_hospital': None,
                        'reason': content[:100],
                        'severity': 'medium',
                        'confidence': 'low'
                    }
                else:
                    return {
                        'is_negative': False,
                        'actual_hospital': None,
                        'reason': content[:100],
                        'severity': 'low',
                        'confidence': 'low'
                    }
        
        except requests.exceptions.Timeout:
            self.logger.error("AI请求超时")
            return self._default_analysis(sentiment)
        except Exception as e:
            self.logger.error(f"AI分析失败: {e}")
            return self._default_analysis(sentiment)
    
    def _build_prompt(self, sentiment, hospital_name):
        """构建AI分析提示词"""
        title = sentiment.get('title', '')
        content = sentiment.get('allContent', '') or sentiment.get('content', '')
        ocr_content = sentiment.get('ocrData', '')
        web_name = sentiment.get('webName', '未知')
        
        # 同时提供正文与OCR，避免OCR过短导致误判
        ocr_min_len = 50
        ocr_note = ""
        if ocr_content and len(ocr_content) < ocr_min_len:
            ocr_note = "（OCR文本较短，仅供参考，不应作为主要判断依据）"
        
        # 限制内容长度
        if len(content) > 1000:
            content = content[:1000]
        if len(ocr_content) > 1000:
            ocr_content = ocr_content[:1000]
        
        feedback_context = self._build_feedback_context()
        rule_hints = self._build_rule_hints()

        prompt = f"""你是一个专业的舆情分析助手。请判断以下内容是否对医院产生真正的负面影响。

判断标准（以下情况视为负面舆情）：
1. 医疗事故、医疗纠纷
2. 服务态度差、收费不合理
3. 隐私泄露（如患者信息外泄）
4. 医护人员不当行为
5. 设备故障、管理混乱
6. 其他损害医院声誉的事件

特别注意（以下情况不属于负面）：
- 中性医疗报道（如医院开展新技术、学术会议）
- 正面新闻（如医院成功救治患者）
- 常规的医疗科普内容
{rule_hints}{feedback_context}

舆情信息：
涉及医院: {hospital_name}
来源: {web_name}
标题: {title}
用户正文（allContent）: {content}
OCR文本（ocrData）: {ocr_content} {ocr_note}

请返回JSON格式（只返回JSON，不要其他内容）:
{{
    "is_negative": true/false,
    "reason": "简要说明判断理由（50字以内）",
    "severity": "high/medium/low"
}}"""
        
        return prompt

    def _apply_feedback_rules(self, sentiment):
        sentiment_id = sentiment.get('id')
        if sentiment_id:
            feedback = self._get_feedback_by_sentiment_id(sentiment_id)
            if feedback is not None:
                return {
                    'is_negative': feedback,
                    'actual_hospital': None,
                    'reason': '已存在用户反馈',
                    'severity': 'low' if not feedback else 'medium',
                    'confidence': 'high'
                }

        rules = self._load_feedback_rules()
        if not rules:
            return None

        text = self._combine_text(sentiment)
        for rule in rules:
            if self._rule_matches(text, rule):
                if rule['action'] == 'exclude':
                    return {
                        'is_negative': False,
                        'actual_hospital': None,
                        'reason': f"匹配反馈规则: {rule['pattern']}",
                        'severity': 'low',
                        'confidence': 'high'
                    }
                if rule['action'] == 'include':
                    return {
                        'is_negative': True,
                        'actual_hospital': None,
                        'reason': f"匹配反馈规则: {rule['pattern']}",
                        'severity': 'medium',
                        'confidence': 'high'
                    }

        return None

    def _get_feedback_by_sentiment_id(self, sentiment_id):
        if not self.db_path:
            return None

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT feedback_judgment FROM sentiment_feedback
                WHERE sentiment_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            ''', (sentiment_id,))
            row = cursor.fetchone()
            conn.close()
            if row is None:
                return None
            return bool(row[0])
        except Exception as e:
            self.logger.error(f"读取反馈失败: {e}")
            return None

    def _load_feedback_rules(self):
        if not self.db_path or not self.feedback_config.get('enable_rules', True):
            return []

        min_conf = self.feedback_config.get('rules_min_confidence', 0.7)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT pattern, rule_type, action, confidence
                FROM feedback_rules
                WHERE enabled = 1 AND confidence >= ?
                ORDER BY confidence DESC, created_at DESC
                LIMIT 50
            ''', (min_conf,))
            rows = cursor.fetchall()
            conn.close()
            return [
                {
                    'pattern': row[0],
                    'rule_type': row[1],
                    'action': row[2],
                    'confidence': row[3]
                }
                for row in rows
            ]
        except Exception as e:
            self.logger.error(f"读取反馈规则失败: {e}")
            return []

    def _rule_matches(self, text, rule):
        if not text:
            return False
        if rule['rule_type'] == 'regex':
            try:
                return re.search(rule['pattern'], text) is not None
            except re.error:
                return False
        return rule['pattern'] in text

    def _combine_text(self, sentiment):
        title = sentiment.get('title', '')
        content = sentiment.get('allContent', '')
        ocr_content = sentiment.get('ocrData', '')
        web_name = sentiment.get('webName', '未知')
        return f"{title}\n{ocr_content}\n{content}\n{web_name}"

    def _build_rule_hints(self):
        if not self.feedback_config.get('enable_rules', True):
            return ''

        rules = self._load_feedback_rules()
        if not rules:
            return ''

        patterns = [rule['pattern'] for rule in rules[:10]]
        return "\n用户反馈规则（命中时优先考虑为非负面或负面）：\n" + "、".join(patterns) + "\n"

    def _build_feedback_context(self):
        if not self.db_path or not self.feedback_config.get('enable_few_shot', True):
            return ''

        limit = self.feedback_config.get('max_few_shot', 5)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT f.sentiment_id, f.feedback_judgment, f.feedback_text,
                       n.title, n.hospital_name, n.source, n.content
                FROM sentiment_feedback f
                LEFT JOIN negative_sentiments n
                ON f.sentiment_id = n.sentiment_id
                ORDER BY f.created_at DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return ''

            lines = ["\n用户反馈示例（供判断参考）："]
            for idx, row in enumerate(rows, 1):
                sentiment_id, judgment, feedback_text, title, hospital, source, content = row
                label = '负面' if judgment else '非负面'
                snippet = (content or '')[:200]
                lines.append(
                    f"案例{idx}: 标题:{title or '无标题'}；医院:{hospital or '未知'}；来源:{source or '未知'}；内容:{snippet}；用户反馈:{feedback_text}；结论:{label}"
                )

            return "\n" + "\n".join(lines) + "\n"
        except Exception as e:
            self.logger.error(f"读取反馈样本失败: {e}")
            return ''
    
    def _default_analysis(self, sentiment):
        """默认分析（当AI不可用时）"""
        attitude = sentiment.get('attitudeMerge', '')
        negative_prob = sentiment.get('negativeProbs', '0')
        
        # 如果API已经标记为负面且概率较高
        if attitude == '-1' and float(negative_prob) > 0.7:
            return {
                'is_negative': True,
                'actual_hospital': None,
                'reason': f"API标记为负面（概率:{negative_prob}）",
                'severity': 'medium',
                'confidence': 'low'
            }
        else:
            return {
                'is_negative': False,
                'actual_hospital': None,
                'reason': "API未标记为负面或概率较低",
                'severity': 'low',
                'confidence': 'low'
            }

if __name__ == '__main__':
    # 测试代码
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    analyzer = SentimentAnalyzer(config)
    
    # 测试舆情数据
    test_sentiment = {
        'title': '网红疑患性病病历流传',
        'allContent': '医院东莞市第九人民医院的病历在网络流传...',
        'ocrData': '医院东莞市第九人民医院的病历在网络流传',
        'webName': '抖音',
        'attitudeMerge': '-1',
        'negativeProbs': '0.91'
    }
    
    hospital_name = "东莞市第九人民医院"
    
    result = analyzer.analyze(test_sentiment, hospital_name)
    
    print("\nAI分析结果:")
    print(f"  是否负面: {result['is_negative']}")
    print(f"  理由: {result['reason']}")
    print(f"  严重程度: {result['severity']}")
    print(f"  置信度: {result['confidence']}")
