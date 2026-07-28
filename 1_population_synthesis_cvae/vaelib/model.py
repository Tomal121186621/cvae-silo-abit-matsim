"""Simple conditional VAE (Borysov 2019 style) — flat one-hot, PUMA embedding, MLP enc/dec,
one-shot softmax heads, Gaussian latent with free-bits. All-categorical (income binned).

No autoregressive decoder, no transformer, no income head. Joints are carried by the latent.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import torch
import torch.nn as nn
import torch.nn.functional as F

from . import config


# ── variable schema (name, n_cats, base) ─────────────────────────────────
def hh_cat_vars():
    return [("dwellingType", config.N_DWELLING_TYPES, 1),
            ("tenure", config.N_TENURE, 1),
            ("autos", config.N_AUTOS, 0),
            ("income_bin", config.n_hh_income_bins(), 0)]


def pp_cat_vars():
    return [("age_bin", config.N_AGE_BINS, 0),
            ("gender", config.N_GENDER, 1),
            ("race", config.N_RACE, 1),
            ("occupation", config.N_OCCUPATION, 1),
            ("driversLicense", config.N_LICENSE, 0),
            ("relationship", config.N_RELATIONSHIP, 0),
            ("nationality", config.N_NATIONALITY, 1),
            ("income_bin", config.n_pp_income_bins(), 0)]


@dataclass
class CVAEConfig:
    latent_dim: int = 24
    puma_embed_dim: int = 8
    hidden_dim: int = 256
    enc_depth: int = 2
    dec_depth: int = 2
    dropout: float = 0.0
    free_bits: float = 0.5          # nats/dim floor on KL (anti-collapse)
    w_marginal: float = 0.0         # per-PUMA marginal-JSD weight (ablated)


@dataclass
class CVAEBatch:
    hh_idx: torch.Tensor      # (B, K_hh) long, 0-indexed
    pp_idx: torch.Tensor      # (B, S_MAX, K_pp) long, 0-indexed
    pp_mask: torch.Tensor     # (B, S_MAX) bool
    puma_idx: torch.Tensor    # (B,) long
    size_idx: torch.Tensor    # (B,) long, 1..S_MAX
    w: torch.Tensor           # (B,) float


def _mlp(d_in, d_out, hidden, depth, dropout):
    layers, d = [], d_in
    for _ in range(depth):
        layers += [nn.Linear(d, hidden), nn.LayerNorm(hidden), nn.GELU()]
        if dropout > 0:
            layers.append(nn.Dropout(dropout))
        d = hidden
    layers.append(nn.Linear(d, d_out))
    return nn.Sequential(*layers)


class CVAE(nn.Module):
    def __init__(self, n_pumas: int, cfg: CVAEConfig | None = None):
        super().__init__()
        self.cfg = cfg or CVAEConfig()
        self.S = config.S_MAX
        self.hh_vars = hh_cat_vars()
        self.pp_vars = pp_cat_vars()
        self.sum_hh = sum(n for _, n, _ in self.hh_vars)
        self.sum_pp = sum(n for _, n, _ in self.pp_vars)
        self.n_size = config.N_HH_SIZES

        self.puma_emb = nn.Embedding(n_pumas, self.cfg.puma_embed_dim)
        cond_dim = self.cfg.puma_embed_dim + self.n_size           # PUMA emb + size one-hot

        enc_in = self.sum_hh + self.S * self.sum_pp + cond_dim
        self.enc = _mlp(enc_in, 2 * self.cfg.latent_dim, self.cfg.hidden_dim,
                        self.cfg.enc_depth, self.cfg.dropout)

        self.dec = _mlp(self.cfg.latent_dim + cond_dim, self.cfg.hidden_dim,
                        self.cfg.hidden_dim, self.cfg.dec_depth, self.cfg.dropout)
        # one-shot heads
        self.hh_heads = nn.ModuleList([nn.Linear(self.cfg.hidden_dim, n) for _, n, _ in self.hh_vars])
        # person head: shared MLP over (hidden ⊕ slot one-hot) → all person var logits
        self.pp_head = _mlp(self.cfg.hidden_dim + self.S, self.sum_pp,
                            self.cfg.hidden_dim, 1, self.cfg.dropout)

    # ── encoding ──────────────────────────────────────────────────────────
    def _cond(self, puma_idx, size_idx):
        size_oh = F.one_hot((size_idx - 1).clamp(0, self.n_size - 1), self.n_size).float()
        return torch.cat([self.puma_emb(puma_idx), size_oh], dim=-1)

    def _onehot_hh(self, hh_idx):
        outs = [F.one_hot(hh_idx[:, k], n).float() for k, (_, n, _) in enumerate(self.hh_vars)]
        return torch.cat(outs, dim=-1)                            # (B, sum_hh)

    def _onehot_pp(self, pp_idx, pp_mask):
        B = pp_idx.shape[0]
        outs = [F.one_hot(pp_idx[:, :, k], n).float() for k, (_, n, _) in enumerate(self.pp_vars)]
        x = torch.cat(outs, dim=-1)                               # (B, S, sum_pp)
        x = x * pp_mask.unsqueeze(-1).float()                     # zero padded slots
        return x.reshape(B, self.S * self.sum_pp)

    def encode(self, b: CVAEBatch):
        x = torch.cat([self._onehot_hh(b.hh_idx), self._onehot_pp(b.pp_idx, b.pp_mask),
                       self._cond(b.puma_idx, b.size_idx)], dim=-1)
        mu, logvar = self.enc(x).chunk(2, dim=-1)
        return mu, logvar.clamp(-8, 8)

    def decode(self, z, puma_idx, size_idx):
        h = self.dec(torch.cat([z, self._cond(puma_idx, size_idx)], dim=-1))   # (B, H)
        hh_logits = [head(h) for head in self.hh_heads]
        B = h.shape[0]
        slot_oh = torch.eye(self.S, device=h.device).unsqueeze(0).expand(B, -1, -1)  # (B,S,S)
        h_rep = h.unsqueeze(1).expand(-1, self.S, -1)                                # (B,S,H)
        pp_flat = self.pp_head(torch.cat([h_rep, slot_oh], dim=-1))                  # (B,S,sum_pp)
        pp_logits = list(torch.split(pp_flat, [n for _, n, _ in self.pp_vars], dim=-1))
        return hh_logits, pp_logits

    # ── losses ────────────────────────────────────────────────────────────
    def compute_loss(self, b: CVAEBatch, beta: float = 1.0, marg=None):
        mu, logvar = self.encode(b)
        z = mu + torch.randn_like(mu) * (0.5 * logvar).exp()
        hh_logits, pp_logits = self.decode(z, b.puma_idx, b.size_idx)
        w = b.w / b.w.sum().clamp_min(1e-8)

        recon = torch.zeros(b.hh_idx.shape[0], device=mu.device)
        for k, lg in enumerate(hh_logits):
            recon = recon + F.cross_entropy(lg, b.hh_idx[:, k], reduction="none")
        for k, lg in enumerate(pp_logits):
            ce = F.cross_entropy(lg.reshape(-1, lg.shape[-1]), b.pp_idx[:, :, k].reshape(-1),
                                 reduction="none").reshape(b.pp_idx.shape[0], self.S)
            recon = recon + (ce * b.pp_mask.float()).sum(dim=1)
        recon = (recon * w).sum()

        # KL with free-bits (per-dim floor → forces the latent to be used)
        kl_dim = -0.5 * (1 + logvar - mu.pow(2) - logvar.exp())          # (B, D)
        kl_dim_mean = (kl_dim * w.unsqueeze(-1)).sum(dim=0)              # (D,)
        kl = kl_dim_mean.clamp_min(self.cfg.free_bits).sum()
        active = int((kl_dim_mean > 0.01).sum().item())

        loss = recon + beta * kl
        jsd = torch.tensor(0.0, device=mu.device)
        if self.cfg.w_marginal > 0 and marg is not None:
            jsd = self._marginal_jsd(b, marg)
            loss = loss + self.cfg.w_marginal * jsd
        return loss, {"recon": float(recon.detach()), "kl": float(kl.detach()),
                      "jsd": float(jsd.detach()), "kl_active_dims": active,
                      "kl_dim_max": float(kl_dim_mean.detach().max())}

    def _marginal_jsd(self, b: CVAEBatch, marg: dict):
        """Per-PUMA marginal JSD from PRIOR samples vs target marginals.
        `marg` = {var_name: (n_pumas, n_cats) tensor} aligned to puma_idx."""
        z = torch.randn(b.hh_idx.shape[0], self.cfg.latent_dim, device=b.w.device)
        hh_logits, pp_logits = self.decode(z, b.puma_idx, b.size_idx)
        n_pumas = next(iter(marg.values())).shape[0]
        total = torch.tensor(0.0, device=b.w.device); count = 0

        def agg(probs, pid, weights, n_cats):
            g = torch.zeros(n_pumas, n_cats, device=probs.device)
            g.index_add_(0, pid, probs * weights.unsqueeze(-1))
            s = g.sum(dim=1, keepdim=True)
            return g, s.squeeze(-1)

        def jsd(p, q):
            m = 0.5 * (p + q)
            kl = lambda a, b_: (a * (a.clamp_min(1e-9).log() - b_.clamp_min(1e-9).log())).sum(-1)
            return 0.5 * kl(p, m) + 0.5 * kl(q, m)

        for k, (name, n, _) in enumerate(self.hh_vars):
            key = "income_bin" if name == "income_bin" else name
            if key not in marg: continue
            probs = F.softmax(hh_logits[k], dim=-1)
            g, sm = agg(probs, b.puma_idx, b.w, n)
            valid = sm > 0
            if valid.any():
                gp = g[valid] / sm[valid].unsqueeze(-1)
                total = total + jsd(gp, marg[key][valid]).mean(); count += 1
        pid_pp = b.puma_idx.unsqueeze(1).expand(-1, self.S).reshape(-1)
        mask_flat = b.pp_mask.reshape(-1)
        wp = (b.w.unsqueeze(1).expand(-1, self.S).reshape(-1)) * mask_flat.float()
        for k, (name, n, _) in enumerate(self.pp_vars):
            key = "pp_income_bin" if name == "income_bin" else name
            if key not in marg: continue
            probs = F.softmax(pp_logits[k], dim=-1).reshape(-1, n)
            g, sm = agg(probs, pid_pp, wp, n)
            valid = sm > 0
            if valid.any():
                gp = g[valid] / sm[valid].unsqueeze(-1)
                total = total + jsd(gp, marg[key][valid]).mean(); count += 1
        return total / max(count, 1)

    # ── sampling (raw draws; constraints + exact age applied in generate.py) ──
    @torch.no_grad()
    def sample(self, puma_idx, size_idx, temperature: float = 1.0):
        z = torch.randn(len(puma_idx), self.cfg.latent_dim, device=self.puma_emb.weight.device)
        hh_logits, pp_logits = self.decode(z, puma_idx, size_idx)
        hh = torch.stack([torch.multinomial(F.softmax(lg / temperature, -1), 1).squeeze(-1)
                          for lg in hh_logits], dim=1)                       # (B, K_hh)
        pp = []
        for lg in pp_logits:                                                # each (B,S,n)
            B, S, n = lg.shape
            s = torch.multinomial(F.softmax(lg.reshape(-1, n) / temperature, -1), 1).reshape(B, S)
            pp.append(s)
        pp = torch.stack(pp, dim=-1)                                        # (B, S, K_pp)
        return hh, pp
