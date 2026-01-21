#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI舆情分析模块
使用智谱AI判断舆情是否为负面
"""

import requests
import json
import yaml
import logging

class SentimentAnalyzer:
    def __init__(self, config):
        self.config = config['ai']
        self.provider = self.config['provider']
        self.model = self.config['model']
        self.api_key = self.config['api_key']
        self.api_url = self.config['api_url']
        self.temperature = self.config.get('temperature', 0.3)
        self.max_tokens = self.config.get('max_tokens', 500)
        
        self.logger = logging.getLogger(__name__)
    
    def analyze(self, sentiment, hospital_name):
        """分析舆情是否为负面"""
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
        content = sentiment.get('allContent', '')
        ocr_content = sentiment.get('ocrData', '')
        web_name = sentiment.get('webName', '未知')
        
        # 优先使用OCR内容，因为可能更准确
        text_content = ocr_content if ocr_content else content
        
        # 限制内容长度
        if len(text_content) > 1000:
            text_content = text_content[:1000]
        
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

舆情信息：
涉及医院: {hospital_name}
来源: {web_name}
标题: {title}
内容: {text_content}

请返回JSON格式（只返回JSON，不要其他内容）:
{{
    "is_negative": true/false,
    "reason": "简要说明判断理由（50字以内）",
    "severity": "high/medium/low"
}}"""
        
        return prompt
    
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
