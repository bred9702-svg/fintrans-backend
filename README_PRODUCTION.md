# MuniaPay - Guide de passage en production

Ce document liste toutes les étapes nécessaires pour passer le backend de la sandbox vers la production.

## Pré-requis

Avant de passer en production, vérifier :

- [ ] Entité légale créée (SARL RDC ou Limited Company Kenya)
- [ ] Compte bancaire business opérationnel
- [ ] Licence Money Remittance obtenue (BCC pour RDC, CBK pour Kenya)
- [ ] KYB (Know Your Business) validé par Pawapay
- [ ] Capital de réserve disponible sur les wallets Pawapay
- [ ] Politique AML/KYC documentée
- [ ] CGU et politique de confidentialité publiées sur le site
- [ ] Custom domain configuré (muniapay.com)

## Variables d'environnement à modifier sur Render

Aller sur Render → Service `fintrans-backend` → onglet **Environment**

### Variables à modifier

| Variable | Sandbox (actuel) | Production |
|----------|------------------|------------|
| `PAWAPAY_URL` | `https://api.sandbox.pawapay.cloud` | `https://api.pawapay.cloud` |
| `PAWAPAY_TOKEN` | Token sandbox actuel | Nouveau token production (à générer dans Pawapay dashboard production) |
| `CHECK_BALANCE` | (non défini, donc false) | `true` |

### Variables à laisser identiques

- `SUPABASE_URL` (même base de données pour les transactions)
- `SUPABASE_KEY` (même clé)

## Vérifications post-déploiement

0. Après avoir changé les variables, Render redéploie automatiquement. Tester :

Mettre à jour CORS dans app.py avec le custom domain quand muniapay.com est configuré.

1. **Faire un transfert test de 1 USD** depuis ton propre numéro Mobile Money
2. **Vérifier les logs Render** pour s'assurer que :
   - `PAWAPAY DEPOSIT RESPONSE` retourne `ACCEPTED`
   - `WALLET BALANCES` est appelé et retourne les vrais soldes
3. **Vérifier que l'argent arrive** sur le numéro de destination
4. **Vérifier les frais perçus** dans le wallet Pawapay

## Configuration Pawapay production

Sur le dashboard Pawapay production (différent du sandbox) :

- [ ] Régénérer un nouveau token API
- [ ] Configurer les **Callback URLs** :
  - Deposits → `https://fintrans-backend.onrender.com/webhook/deposit`
  - Payouts → `https://fintrans-backend.onrender.com/webhook/payout`
  - Refunds → `https://fintrans-backend.onrender.com/webhook/refund`
- [ ] Pré-financer les wallets KES et USD avec le capital de réserve

## Fonctionnalités à ajouter avant production

- [ ] Live exchange rates (remplacer `RATES = {"RDC_TO_KEN": 129.50}` par appel API)
- [ ] Notifications WhatsApp Business API (expéditeur + bénéficiaire)
- [ ] KYC utilisateur pour transferts > 1000 USD (vérification identité)
- [ ] Rate limiting (anti-spam)
- [ ] Captcha sur le formulaire
- [ ] Réactiver Row Level Security (RLS) sur Supabase avec policies adaptées
- [ ] Validation backend des limites de montant (actuellement uniquement frontend)
- [ ] Logs et monitoring (Sentry, LogRocket ou équivalent)
- [ ] Conversion automatique entre wallets USD ↔ KES si l'un est bas

## Notes

- Le code actuel utilise `CHECK_BALANCE` comme flag. En sandbox il est désactivé pour permettre les tests même si les wallets sont vides.
- Les correspondents Pawapay (`AIRTEL_COD`, `MPESA_KEN`) sont les mêmes en sandbox et en production.
- Le `customerTimestamp` est obligatoire pour tous les appels.
- Les montants vers M-Pesa Kenya ne supportent pas les décimales — le code gère déjà ce cas.

## Contact support Pawapay

Si problèmes en production : ouvrir un ticket via le dashboard production → Help → Support.
Le support sandbox n'est pas disponible (uniquement production).
