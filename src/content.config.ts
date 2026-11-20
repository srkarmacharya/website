import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const research = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/research' }),
  schema: z.object({
    plainTitle: z.string(),
    title: z.string(),
    authors: z.string(),
    journal: z.string(),
    year: z.number(),
    citation: z.string(),
    doi: z.string(),
    license: z.string().optional(),
    summary: z.string(),
    order: z.number(),
    explainer: z.boolean().default(true),
  }),
});

const opinions = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/opinions' }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    summary: z.string().optional(),
    draft: z.boolean().default(false),
    // 'project' = written for a project (e.g. Rupantar); 'opinion' = personal view
    kind: z.enum(['opinion', 'project']).default('opinion'),
    originalTitle: z.string().optional(),
    originalUrl: z.string().url().optional(),
    originalSource: z.string().optional(),
  }),
});

export const collections = { research, opinions };
