<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aplicacao</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #ffffff; color: #333333; font-family: system-ui, sans-serif; line-height: 1.6; }
        .container { max-width: 600px; margin: 40px auto; padding: 24px; background: #f5f5f5; border-radius: 12px; }
        h1 { font-size: 1.5rem; margin-bottom: 16px; }
        input, select, textarea { width: 100%; padding: 10px; margin: 8px 0; background: #ffffff; color: #333333; border: 1px solid #ced4da; border-radius: 6px; font-size: 1rem; }
        button { background: #007bff; color: #fff; padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 1rem; }
        button:hover { opacity: 0.9; }
        .result { margin-top: 16px; padding: 16px; background: #ffffff; border-radius: 6px; }
    
        @media (max-width: 768px) {
            .calculator { width: 95%; margin: 10px auto; padding: 15px; }
            .display { font-size: 1.8rem; height: 50px; }
            button { height: 45px; font-size: 1rem; }
            .botoes { grid-template-columns: repeat(4, 1fr); gap: 8px; }
        }
</style>
</head>
<body>
    <div class="container">
        <h1>Calculadora</h1>
        <input type="number" id="valor" placeholder="Valor">
        <button onclick="calcular()">Calcular</button>
        <div id="resultado" class="result"></div>
    </div>
    <script>
        function calcular() {
            const v = parseFloat(document.getElementById('valor').value) || 0;
            document.getElementById('resultado').innerHTML = 'Resultado: R$ ' + v.toFixed(2);
        }
    </script>
</body>
</html>