// 问题翻译映射表 - 将英文问题翻译为中文显示
const QUESTION_TRANSLATIONS = {
  // 基础数学问题
  "What is 2 + 2?": "2 + 2 等于多少？",
  "What is the area of a circle with radius 5?": "半径为 5 的圆的面积是多少？",
  "Explain the Pythagorean theorem": "请解释勾股定理",
  "What is the derivative of x^2?": "x² 的导数是多少？",
  "How do you solve a quadratic equation?": "如何解二次方程？",
  
  // 物理问题
  "What is Newton's second law?": "牛顿第二定律是什么？",
  "Explain the concept of energy": "请解释能量的概念",
  "What is the speed of light?": "光速是多少？",
  
  // 编程问题
  "What is a variable in programming?": "编程中的变量是什么？",
  "Explain object-oriented programming": "请解释面向对象编程",
  "What is a loop?": "什么是循环？",
  "How does recursion work?": "递归是如何工作的？",
  
  // 通用学习问题
  "Can you explain this concept in simpler terms?": "能用更简单的术语解释这个概念吗？",
  "What are the key points?": "关键点是什么？",
  "Can you give me an example?": "能给我一个例子吗？",
  "I don't understand, can you clarify?": "我不理解，能澄清一下吗？",
  "What is the practical application?": "实际应用是什么？",
  "How do I choose the rule?": "我应该如何选择规则？",
  "Could you provide another example with different conditions?": "能给我一个条件不同的例子吗？",
  "What should I check to verify my answer?": "我应该检查什么来验证答案？",
  "Can I try a transfer problem independently?": "我能独立尝试一道迁移题吗？",
  "How do I identify the core condition versus distractions?": "如何识别核心条件和干扰信息？",
  "What are the key checkpoints for this process?": "这个过程的关键检查点是什么？",
};

/**
 * 将英文问题翻译为中文显示
 * @param {string} englishQuestion - 英文问题
 * @returns {string} - 中文翻译，如果没有找到翻译则返回原文
 */
export function translateQuestion(englishQuestion) {
  if (!englishQuestion || typeof englishQuestion !== 'string') {
    return englishQuestion;
  }

  const trimmed = englishQuestion.trim();
  
  // 如果已经是中文，直接返回
  if (/[\u4e00-\u9fa5]/.test(trimmed)) {
    return trimmed;
  }

  // 精确匹配
  if (QUESTION_TRANSLATIONS[trimmed]) {
    return QUESTION_TRANSLATIONS[trimmed];
  }

  // 智能翻译：识别常见的学习对话模式
  const smartPatterns = [
    // "I think I can..." 模式（精确匹配）
    { 
      pattern: /^I think I can use the rule for (.+), but I will (.+)\.?$/i, 
      template: (m) => `我认为可以使用${m[1]}的规则，但我会${m[2]}。`
    },
    { 
      pattern: /^I think I can (.+), but (.+)\.?$/i, 
      template: (m) => `我认为我可以${m[1]}，但是${m[2]}。`
    },
    { 
      pattern: /^I think (.+)\.?$/i, 
      template: (m) => `我认为${m[1]}。`
    },
    
    // "I see..." 模式
    { 
      pattern: /^I see that (.+)\. I think I need to (.+)\.?$/i, 
      template: (m) => `我明白了${m[1]}。我觉得我需要${m[2]}。`
    },
    { 
      pattern: /^I see (.+)\.?$/i, 
      template: (m) => `我明白了${m[1]}。`
    },
    
    // "I understand..." 模式
    { 
      pattern: /^I understand that (.+)\.?$/i, 
      template: (m) => `我理解${m[1]}。`
    },
    { 
      pattern: /^I understand (.+)\.?$/i, 
      template: (m) => `我明白${m[1]}。`
    },
    
    // "I will..." 模式
    { 
      pattern: /^I will still (.+)\.?$/i, 
      template: (m) => `我仍然会${m[1]}。`
    },
    { 
      pattern: /^I will (.+)\.?$/i, 
      template: (m) => `我将${m[1]}。`
    },
    { 
      pattern: /^I'll try to (.+)\.?$/i, 
      template: (m) => `我会尝试${m[1]}。`
    },
    
    // "I can..." 模式
    { 
      pattern: /^I can (.+)\.?$/i, 
      template: (m) => `我能够${m[1]}。`
    },
    
    // "I need to..." 模式
    { 
      pattern: /^I need to clearly (.+)\.?$/i, 
      template: (m) => `我需要清楚地${m[1]}。`
    },
    { 
      pattern: /^I need to (.+)\.?$/i, 
      template: (m) => `我需要${m[1]}。`
    },
    
    // 问句模式
    { 
      pattern: /^How do I (.+)\?$/i, 
      template: (m) => `我该如何${m[1]}？`
    },
    { 
      pattern: /^How (.+)\?$/i, 
      template: (m) => `如何${m[1]}？`
    },
    { 
      pattern: /^What (.+)\?$/i, 
      template: (m) => `什么${m[1]}？`
    },
    { 
      pattern: /^Can you (.+)\?$/i, 
      template: (m) => `你能${m[1]}吗？`
    },
    { 
      pattern: /^Could you (.+)\?$/i, 
      template: (m) => `您能${m[1]}吗？`
    },
    { 
      pattern: /^Should I (.+)\?$/i, 
      template: (m) => `我应该${m[1]}吗？`
    },
    
    // 请求模式
    { 
      pattern: /^Please (.+)\.?$/i, 
      template: (m) => `请${m[1]}。`
    },
  ];

  for (const { pattern, template } of smartPatterns) {
    const match = trimmed.match(pattern);
    if (match) {
      console.log('[智能翻译匹配]', { 原文: trimmed, 模式: pattern.source });
      return template(match);
    }
  }

  // 通用翻译规则：替换常见词汇
  let translated = trimmed;
  const commonPhrases = {
    'arithmetic sequence': '等差数列',
    'common difference': '公差',
    'first term': '首项',
    'the rule': '规则',
    'key step': '关键步骤',
    'carefully': '仔细地',
    'step by step': '一步一步地',
    'the teacher pointed out': '老师指出',
    'I might confuse': '我可能会混淆',
    'clearly list': '清楚地列出',
    'the knowns': '已知条件',
    'the target': '目标',
    'before starting': '开始之前',
    'for example': '例如',
    'if I have a sequence like': '如果我有一个类似的数列',
  };
  
  for (const [en, zh] of Object.entries(commonPhrases)) {
    translated = translated.replace(new RegExp(en, 'gi'), zh);
  }
  
  // 如果翻译后不同，返回翻译结果
  if (translated !== trimmed) {
    console.log('[短语翻译成功]', { 原文: trimmed, 译文: translated });
    return translated;
  }
  
  // 如果没有匹配的翻译，返回原文
  console.log('[翻译失败 - 无匹配模式]', trimmed);
  return trimmed;
}

/**
 * 批量翻译问题列表
 * @param {string[]} questions - 问题数组
 * @returns {string[]} - 翻译后的问题数组
 */
export function translateQuestions(questions) {
  if (!Array.isArray(questions)) {
    return questions;
  }
  return questions.map(q => translateQuestion(q));
}

/**
 * 添加新的翻译映射（运行时动态添加）
 * @param {string} english - 英文问题
 * @param {string} chinese - 中文翻译
 */
export function addTranslation(english, chinese) {
  QUESTION_TRANSLATIONS[english.trim()] = chinese.trim();
}

/**
 * 获取所有翻译映射（用于调试）
 * @returns {Object} - 所有翻译映射
 */
export function getAllTranslations() {
  return { ...QUESTION_TRANSLATIONS };
}
