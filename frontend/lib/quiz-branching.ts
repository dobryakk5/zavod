import type { QuizBuilderResultCondition, QuizBuilderResultRule, QuizBuilderScreen } from './api/quiz-builder';

export type UserAnswer = {
  optionIds?: string[];
  number?: number;
  text?: string;
};

export type UserAnswersMap = Record<string, UserAnswer>;

function toScreenId(value: number | string | undefined | null): string {
  if (value === undefined || value === null) return '';
  return String(value);
}

function normalizeValues(values: string[] | undefined): string[] {
  return Array.isArray(values) ? values.map((item) => String(item)) : [];
}

export function resolveNextScreen(
  currentScreen: QuizBuilderScreen,
  selectedOptionId: string | undefined,
  allScreens: QuizBuilderScreen[],
): QuizBuilderScreen | null {
  const currentId = toScreenId(currentScreen.id);
  const currentIndex = allScreens.findIndex((screen) => toScreenId(screen.id) === currentId);

  if (
    currentScreen.kind === 'question'
    && currentScreen.questionType === 'single'
    && selectedOptionId
  ) {
    const option = (currentScreen.options || []).find((item) => toScreenId(item.id) === selectedOptionId);

    if (option?.nextSpecial === '__lead') {
      return allScreens.find((screen) => screen.kind === 'lead') || null;
    }

    if (option?.nextSpecial === '__end') {
      return resolveResult(allScreens, {});
    }

    if (option?.nextScreenId !== undefined && option?.nextScreenId !== null && option.nextScreenId !== '') {
      const target = allScreens.find((screen) => toScreenId(screen.id) === toScreenId(option.nextScreenId));
      if (target) return target;
    }
  }

  if (currentIndex === -1) return null;
  return allScreens[currentIndex + 1] || null;
}

export function resolveResult(allScreens: QuizBuilderScreen[], answers: UserAnswersMap): QuizBuilderScreen | null {
  const resultScreens = allScreens.filter((screen) => screen.kind === 'result');

  for (const screen of resultScreens) {
    if (screen.isDefaultResult) continue;

    const rules = Array.isArray(screen.rules) ? [...screen.rules] : [];
    for (const rule of rules.sort((a, b) => (a.position || 0) - (b.position || 0))) {
      if (ruleMatches(rule, answers)) {
        return screen;
      }
    }
  }

  return resultScreens.find((screen) => screen.isDefaultResult) || resultScreens[resultScreens.length - 1] || null;
}

function ruleMatches(rule: QuizBuilderResultRule, answers: UserAnswersMap): boolean {
  return (rule.conditions || []).every((condition) => conditionMatches(condition, answers));
}

function conditionMatches(condition: QuizBuilderResultCondition, answers: UserAnswersMap): boolean {
  const screenId = toScreenId(condition.screenId);
  const answer = answers[screenId];
  if (!answer) return false;

  const conditionValues = normalizeValues(condition.value);

  switch (condition.operator) {
    case 'includes':
      return conditionValues.some((value) => (answer.optionIds || []).includes(value));
    case 'not_includes':
      return conditionValues.every((value) => !(answer.optionIds || []).includes(value));
    case 'gte':
      return (answer.number ?? -Infinity) >= Number(conditionValues[0]);
    case 'lte':
      return (answer.number ?? Infinity) <= Number(conditionValues[0]);
    case 'equals':
      if (Array.isArray(answer.optionIds)) {
        return answer.optionIds.length === conditionValues.length
          && conditionValues.every((value) => answer.optionIds?.includes(value));
      }
      if (answer.number !== undefined) {
        return answer.number === Number(conditionValues[0]);
      }
      if (answer.text !== undefined) {
        return answer.text === conditionValues[0];
      }
      return false;
    default:
      return false;
  }
}
