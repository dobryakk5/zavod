curl -s -X POST "https://router.huggingface.co/models/runwayml/stable-diffusion-v1-5" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"inputs":"A fantasy landscape, sunrise over mountains","options":{"wait_for_model":true}}' \
  --output result.png
