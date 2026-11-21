import React, { useState, useEffect } from 'react';
import './AttackDashboard.css';

const AttackDashboard = () => {
  const [evalData, setEvalData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadEvalData();
  }, []);

  const loadEvalData = async () => {
    try {
      const response = await fetch('/api/attack-eval-results');
      const data = await response.json();
      setEvalData(data);
      setLoading(false);
    } catch (error) {
      console.error('加载评估数据失败:', error);
      // 使用模拟数据
      setEvalData(getMockData());
      setLoading(false);
    }
  };

  const getMockData = () => ({
    public: {
      membership_inference: { asr: 0.140, defense_rate: 0.860 },
      model_inversion: { asr: 0.060, defense_rate: 0.440 },
      copyright_extraction: { asr: 0.000, defense_rate: 0.810 },
      prompt_injection: { asr: 0.000, defense_rate: 1.000 }
    },
    custom: {
      membership_inference: { asr: 0.080, defense_rate: 0.920 },
      model_inversion: { asr: 0.000, defense_rate: 1.000 },
      copyright_extraction: { asr: 0.000, defense_rate: 1.000 },
      prompt_injection: { asr: 0.000, defense_rate: 1.000 }
    }
  });

  const attackTypes = {
    membership_inference: '会员推理攻击',
    model_inversion: '模型反演攻击',
    copyright_extraction: '版权提取攻击',
    prompt_injection: '提示注入攻击'
  };

  if (loading) return <div className="dashboard-loading">加载中...</div>;

  return (
    <div className="attack-dashboard">
      <h1>隐私攻击防御看板</h1>
      
      <div className="dataset-comparison">
        <div className="dataset-section">
          <h2>公开数据集 (MMLU/GSM8K)</h2>
          <div className="metrics-grid">
            {Object.entries(attackTypes).map(([key, name]) => (
              <MetricCard
                key={key}
                title={name}
                asr={evalData.public[key].asr}
                defenseRate={evalData.public[key].defense_rate}
              />
            ))}
          </div>
        </div>

        <div className="dataset-section">
          <h2>自建数据集 (教育场景)</h2>
          <div className="metrics-grid">
            {Object.entries(attackTypes).map(([key, name]) => (
              <MetricCard
                key={key}
                title={name}
                asr={evalData.custom[key].asr}
                defenseRate={evalData.custom[key].defense_rate}
              />
            ))}
          </div>
        </div>
      </div>

      <ComparisonChart evalData={evalData} attackTypes={attackTypes} />
    </div>
  );
};

const MetricCard = ({ title, asr, defenseRate }) => {
  const defenseColor = defenseRate >= 0.9 ? '#4caf50' : defenseRate >= 0.7 ? '#ff9800' : '#f44336';

  return (
    <div className="metric-card">
      <h3>{title}</h3>
      <div className="metric-values">
        <div className="metric-item">
          <span className="metric-label">攻击成功率</span>
          <span className="metric-value attack">{(asr * 100).toFixed(1)}%</span>
        </div>
        <div className="metric-item">
          <span className="metric-label">防御率</span>
          <span className="metric-value defense" style={{color: defenseColor}}>
            {(defenseRate * 100).toFixed(1)}%
          </span>
        </div>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{width: `${defenseRate * 100}%`, backgroundColor: defenseColor}}></div>
      </div>
    </div>
  );
};

const ComparisonChart = ({ evalData, attackTypes }) => {
  return (
    <div className="comparison-chart">
      <h2>防御率对比</h2>
      <table className="comparison-table">
        <thead>
          <tr>
            <th>攻击类型</th>
            <th>公开数据集</th>
            <th>自建数据集</th>
            <th>提升</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(attackTypes).map(([key, name]) => {
            const publicDefense = evalData.public[key].defense_rate;
            const customDefense = evalData.custom[key].defense_rate;
            const improvement = ((customDefense - publicDefense) / publicDefense * 100).toFixed(1);
            
            return (
              <tr key={key}>
                <td>{name}</td>
                <td>{(publicDefense * 100).toFixed(1)}%</td>
                <td>{(customDefense * 100).toFixed(1)}%</td>
                <td className={improvement > 0 ? 'positive' : 'neutral'}>
                  {improvement > 0 ? '+' : ''}{improvement}%
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default AttackDashboard;
