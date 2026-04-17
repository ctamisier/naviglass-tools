import express from 'express';
import https from 'https';

const app = express();

app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  next();
});

app.get('/fiche', (req, res) => {
  const code = req.query.code;
  if (!code) return res.status(400).json({ error: 'missing code' });

  https
    .get(
      `https://naviglass.saint-gobain-glass.com/api/internet-fiche?code=${code}`,
      {
        headers: {
          'User-Agent': 'Mozilla/5.0',
          Referer: 'https://naviglass.saint-gobain-glass.com/',
        },
      },
      (r) => {
        let data = '';
        r.on('data', (chunk) => (data += chunk));
        r.on('end', () => {
          try {
            res.json(JSON.parse(data));
          } catch (e) {
            res.status(500).json({ error: 'parse error', raw: data });
          }
        });
      },
    )
    .on('error', (e) => res.status(500).json({ error: e.message }));
});

app.listen(3000, () => console.log('listening'));
