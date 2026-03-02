// modules/mes/services/intentRecognizer.ts
// Local stub - no Supabase dependency

export interface UserIntent {
  queryType: string;
  entities: Record<string, any>;
  confidence: number;
  rawQuery: string;
}

export class IntentRecognizer {
  async recognizeIntent(query: string): Promise<UserIntent> {
    return {
      queryType: 'general',
      entities: {},
      confidence: 0.8,
      rawQuery: query,
    };
  }
}

export const intentRecognizer = new IntentRecognizer();
