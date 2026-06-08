import type { GlobalThemeOverrides } from 'naive-ui'

// 主题基线使用“暖白纸面 + 蓝灰科技感点缀”，保留 Notion 式克制排版，但避免过于苍白。
export const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#49617d',
    primaryColorHover: '#5a7593',
    primaryColorPressed: '#3e5269',
    primaryColorSuppl: '#5a7593',
    infoColor: '#49617d',
    successColor: '#2d7a67',
    warningColor: '#b7791f',
    errorColor: '#c65b46',
    borderColor: '#dfd9cf',
    textColorBase: '#1f252b',
    textColor1: '#1f252b',
    textColor2: '#59636f',
    textColor3: '#7b8794',
    bodyColor: '#fbfbfa',
    cardColor: '#ffffff',
    modalColor: '#ffffff',
    tableColor: '#ffffff',
    popoverColor: '#fffdf8',
    hoverColor: 'rgba(73, 97, 125, 0.08)',
    closeIconColor: '#6b7280'
  },
  Layout: {
    color: '#fbfbfa',
    siderColor: '#f4efe6',
    borderColor: '#ededeb'
  },
  Card: {
    borderRadius: '10px',
    colorEmbedded: '#fffdf9',
    borderColor: '#e4ddd2'
  },
  Input: {
    borderRadius: '8px',
    color: '#fffefb',
    colorFocus: '#fffefb'
  },
  Button: {
    borderRadiusTiny: '8px',
    borderRadiusSmall: '8px',
    borderRadiusMedium: '8px',
    borderRadiusLarge: '8px'
  },
  Menu: {
    itemColorActive: 'rgba(73, 97, 125, 0.12)',
    itemColorActiveHover: 'rgba(73, 97, 125, 0.16)',
    itemTextColorActive: '#26313d',
    itemTextColorActiveHover: '#26313d',
    itemIconColorActive: '#26313d'
  },
  Tabs: {
    tabBorderRadius: '8px'
  },
  Tag: {
    borderRadius: '999px'
  }
}
