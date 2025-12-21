// Wizard / 交付流程定义
export const DELIVERY_FLOW_STEPS = [
  {
    id: 'scenario',
    title: '场景与目标确认',
    fields: ['audience', 'answerStyle']
  },
  {
    id: 'data',
    title: '数据源与范围确认',
    fields: ['dataSourceType', 'dataSource']
  },
  {
    id: 'preferences',
    title: '质量/成本/风险偏好',
    fields: ['sloBudget', 'mustCite']
  },
  {
    id: 'deployment',
    title: '上线方式与回滚策略',
    fields: ['deploymentChannel', 'rollbackStrategy']
  }
]
























