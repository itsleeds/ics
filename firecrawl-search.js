const { FirecrawlApp } = require('@mendable/firecrawl-js');

const API_KEY = 'fc-9442ef8431b945d58cfda979201839c2';

async function searchWeb(query, limit = 10) {
  const app = new FirecrawlApp({ apiKey: API_KEY });
  try {
    const result = await app.search(query, { limit });
    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    console.error('Search error:', error.message);
  }
}

const query = process.argv[2];
const limit = process.argv[3] ? parseInt(process.argv[3]) : 10;

if (!query) {
  console.error('Usage: node firecrawl-search.js "query" [limit]');
  process.exit(1);
}

searchWeb(query, limit);