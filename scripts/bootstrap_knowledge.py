#!/usr/bin/env python3
"""Bootstrap de conhecimento inicial para iaglobal.

Povoa STM/LTM/Obsidian com arquiteturas, padrões e exemplos de referência.
"""

import os
from pathlib import Path
from datetime import datetime, timezone

OBSIDIAN_DIR = Path(__file__).parent.parent / "iaglobal" / "obsidian"
LTM_DIR = OBSIDIAN_DIR / "03_Long_Term"
STM_DIR = OBSIDIAN_DIR / "02_Short_Term"

def create_markdown(filename: str, content: str, tags: list = None):
    """Cria arquivo markdown no Obsidian."""
    filepath = LTM_DIR / filename
    tags_str = " ".join([f"#{tag}" for tag in (tags or [])])
    
    full_content = f"""---
tags: {tags_str}
created: {datetime.now(timezone.utc).isoformat()}
type: knowledge
---

{content}
"""
    
    filepath.write_text(full_content, encoding="utf-8")
    print(f"✅ Criado: {filename}")

def bootstrap_architectures():
    """Cria conhecimentos de arquiteturas de referência."""
    
    # Flask API Architecture
    create_markdown(
        "flask_rest_api_architecture.md",
        """# Flask REST API - Architecture Reference

## Estrutura Padrão
```
project/
├── app/
│   ├── __init__.py
│   ├── routes.py
│   ├── models.py
│   └── utils.py
├── tests/
├── requirements.txt
└── config.py
```

## Padrão de Rotas
```python
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/api/resource', methods=['GET'])
def get_resources():
    # Lista todos os recursos
    return jsonify({'data': []})

@app.route('/api/resource/<int:id>', methods=['GET'])
def get_resource(id):
    # Obtém recurso específico
    return jsonify({'data': {}})

@app.route('/api/resource', methods=['POST'])
def create_resource():
    # Cria novo recurso
    data = request.get_json()
    return jsonify({'data': data}), 201

@app.route('/api/resource/<int:id>', methods=['PUT'])
def update_resource(id):
    # Atualiza recurso
    data = request.get_json()
    return jsonify({'data': data})

@app.route('/api/resource/<int:id>', methods=['DELETE'])
def delete_resource(id):
    # Deleta recurso
    return '', 204
```

## Boas Práticas
- Use blueprints para modularização
- Valide inputs com marshmallow ou pydantic
- Trate erros com @app.errorhandler
- Use SQLAlchemy para ORM
- Implemente autenticação JWT

## Segurança
- Valide todos os inputs
- Use HTTPS em produção
- Implemente rate limiting
- Sanitize outputs (XSS protection)
""",
        tags=["flask", "api", "rest", "python", "architecture"]
    )
    
    # FastAPI Architecture
    create_markdown(
        "fastapi_architecture.md",
        """# FastAPI - Modern API Architecture

## Vantagens vs Flask
- Type hints nativos
- Validação automática (Pydantic)
- OpenAPI/Swagger gerado automaticamente
- Async/await nativo
- Performance superior

## Estrutura
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="My API")

class Item(BaseModel):
    name: str
    price: float
    description: Optional[str] = None

@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}

@app.post("/items/")
async def create_item(item: Item):
    return {"item": item}
```

## Padrões
- Use dependências para injeção
- Separe routers por domínio
- Valide com Pydantic schemas
- Documente com docstrings
""",
        tags=["fastapi", "api", "rest", "python", "async"]
    )
    
    # React Frontend
    create_markdown(
        "react_frontend_architecture.md",
        """# React - Frontend Architecture

## Estrutura de Componentes
```
src/
├── components/
│   ├── common/
│   │   ├── Button.jsx
│   │   ├── Input.jsx
│   │   └── Modal.jsx
│   └── features/
│       ├── UserList.jsx
│       └── UserForm.jsx
├── hooks/
│   ├── useFetch.js
│   └── useForm.js
├── services/
│   └── api.js
├── context/
│   └── AppContext.jsx
└── App.jsx
```

## Padrão de Componente Funcional
```jsx
import React, { useState, useEffect } from 'react';

function UserList({ users }) {
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    // Fetch data on mount
    setLoading(false);
  }, []);
  
  if (loading) return <div>Loading...</div>;
  
  return (
    <ul>
      {users.map(user => (
        <li key={user.id}>{user.name}</li>
      ))}
    </ul>
  );
}

export default UserList;
```

## Comunicação com API
```jsx
// services/api.js
const API_BASE = 'http://localhost:5000/api';

export async function fetchUsers() {
  const response = await fetch(`${API_BASE}/users`);
  return response.json();
}

export async function createUser(data) {
  const response = await fetch(`${API_BASE}/users`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return response.json();
}
```

## Boas Práticas
- Componentes pequenos e focados
- Custom hooks para lógica reutilizável
- Context API para estado global
- Error boundaries para tratamento de erros
""",
        tags=["react", "frontend", "javascript", "components"]
    )
    
    # Testing Patterns
    create_markdown(
        "testing_patterns.md",
        """# Testing Patterns - pytest & unittest

## pytest - Padrão Moderno

## Estrutura de Testes
```
tests/
├── test_routes.py
├── test_models.py
├── test_utils.py
└── conftest.py
```

## Padrão Arrange-Act-Assert
```python
import pytest

def test_create_user():
    # Arrange
    user_data = {"name": "John", "email": "john@example.com"}
    
    # Act
    response = client.post("/api/users", json=user_data)
    
    # Assert
    assert response.status_code == 201
    assert response.json()["data"]["name"] == "John"
```

## Fixtures
```python
# conftest.py
import pytest

@pytest.fixture
def sample_user():
    return {"name": "Test", "email": "test@example.com"}

@pytest.fixture
def authenticated_client(client):
    client.headers["Authorization"] = "Bearer token"
    return client
```

## Testando APIs Flask
```python
import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_get_users(client):
    response = client.get('/api/users')
    assert response.status_code == 200
```

## Cobertura de Testes
- Teste happy path
- Teste edge cases (vazio, null, limites)
- Teste error handling (4xx, 5xx)
- Teste autenticação/autorização
- Mock external services
""",
        tags=["testing", "pytest", "unittest", "qa", "patterns"]
    )
    
    # Database Patterns
    create_markdown(
        "database_patterns.md",
        """# Database Design Patterns

## SQLAlchemy ORM - Padrão
```python
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email
        }
```

## Padrão Repository
```python
class UserRepository:
    def __init__(self, session):
        self.session = session
    
    def get_by_id(self, user_id):
        return self.session.query(User).filter(User.id == user_id).first()
    
    def get_all(self):
        return self.session.query(User).all()
    
    def create(self, user_data):
        user = User(**user_data)
        self.session.add(user)
        self.session.commit()
        return user
    
    def update(self, user_id, user_data):
        user = self.get_by_id(user_id)
        for key, value in user_data.items():
            setattr(user, key, value)
        self.session.commit()
        return user
    
    def delete(self, user_id):
        user = self.get_by_id(user_id)
        self.session.delete(user)
        self.session.commit()
```

## Boas Práticas
- Use migrations (Alembic)
- Indexe colunas de busca
- Use foreign keys para integridade
- Normalize até 3NF
- Connection pooling
""",
        tags=["database", "sqlalchemy", "orm", "sql", "patterns"]
    )
    
    # Security Best Practices
    create_markdown(
        "security_best_practices.md",
        """# Security Best Practices

## Autenticação JWT
```python
from flask_jwt_extended import JWTManager, create_access_token, jwt_required

app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET')
jwt = JWTManager(app)

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    # Validate credentials...
    access_token = create_access_token(identity=data['username'])
    return jsonify(access_token=access_token)

@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    return jsonify(msg="Access granted")
```

## Validação de Inputs
```python
from marshmallow import Schema, fields, validate

class UserSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    email = fields.Email(required=True)
    password = fields.Str(
        required=True, 
        validate=validate.Length(min=8),
        load_only=True  # Never serialize to output
    )
```

## Proteção contra SQL Injection
```python
# ❌ WRONG - vulnerable
user = User.query.filter(f"name = '{name}'").first()

# ✅ CORRECT - parameterized
user = User.query.filter(User.name == name).first()
```

## Checklist de Segurança
- [ ] Valide todos os inputs
- [ ] Use prepared statements/ORM
- [ ] Hash senhas (bcrypt/argon2)
- [ ] Implemente rate limiting
- [ ] Use HTTPS
- [ ] Sanitize outputs (XSS)
- [ ] Proteja contra CSRF
- [ ] Log ações críticas
- [ ] Não exponha stack traces
""",
        tags=["security", "jwt", "validation", "authentication", "best-practices"]
    )

if __name__ == "__main__":
    print("🚀 Bootstrap de conhecimento iaglobal...")
    LTM_DIR.mkdir(parents=True, exist_ok=True)
    STM_DIR.mkdir(parents=True, exist_ok=True)
    
    bootstrap_architectures()
    
    print(f"\n✅ Bootstrap completo! {len(list(LTM_DIR.glob('*.md')))} arquivos criados em {LTM_DIR}")
    print("\nAgents agora terão conhecimento de referência para:")
    print("  - Flask/FastAPI APIs")
    print("  - React frontends")
    print("  - Testes com pytest")
    print("  - Database com SQLAlchemy")
    print("  - Segurança e boas práticas")
