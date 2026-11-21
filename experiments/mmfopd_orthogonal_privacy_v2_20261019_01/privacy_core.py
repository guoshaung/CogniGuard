"""Train-only continuous profile and established concept-erasure references.

Experimental branch only. No role-vector privacy claims and no field risk proxy.
"""
from pathlib import Path
import sys, warnings, time
import numpy as np
from sklearn.svm import LinearSVC

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / 'vendor'))


class ProfileEncoding:
    def __init__(self, fields):
        self.fields = list(fields)

    def raw(self, rows):
        return np.array([[r['values'][k] if r['values'][k] is not None
                          else np.nan for k in self.fields] for r in rows], dtype=float)

    def fit(self, train):
        a = self.raw(train)
        self.medians = np.nanmedian(a, axis=0)
        assert np.isfinite(self.medians).all()
        v = np.concatenate([np.where(np.isnan(a), self.medians, a), np.isnan(a)], axis=1)
        self.mean = v.mean(0)
        sd = v.std(0)
        self.constant_coordinates = np.flatnonzero(sd < 1e-12).tolist()
        self.scale = np.where(sd < 1e-12, 1., sd)
        return self

    def transform(self, rows):
        a = self.raw(rows)
        v = np.concatenate([np.where(np.isnan(a), self.medians, a), np.isnan(a)], axis=1)
        return (v - self.mean) / self.scale

    def description(self):
        return {'dimensions': [{'index': i, 'meaning': prefix + k}
                                for prefix, offset in [('value:', 0), ('missing:', len(self.fields))]
                                for i, k in enumerate(self.fields, start=offset)],
                'train_medians': self.medians.tolist(), 'train_mean': self.mean.tolist(),
                'train_scale': self.scale.tolist(), 'constant_coordinates': self.constant_coordinates,
                'contains': '13 safe numeric inputs and13 availability indicators; no labels/IDs/public calendar',
                'missing': 'train-median imputation plus binary missingness indicator'}


def column_basis(a, tol=1e-10):
    u, s, _ = np.linalg.svd(a, full_matrices=False)
    return u[:, s > tol]


def crosscov(x, s):
    return (x - x.mean(0)).T @ (s - s.mean(0)) / (len(x) - 1)


def fit_projections(z_train, sensitive_train):
    """All input rows are TRAIN. Eval labels are not accepted by this API."""
    import torch
    from concept_erasure import LeaceEraser
    torch.set_num_threads(1)
    start = time.perf_counter()
    dim = z_train.shape[1]
    cov = crosscov(z_train, sensitive_train)
    u = column_basis(cov)
    p = np.eye(dim) - u @ u.T
    xt = torch.tensor(z_train, dtype=torch.float64)
    st = torch.tensor(sensitive_train, dtype=torch.float64)
    opts = dict(affine=True, shrinkage=False, constrain_cov_trace=False, svd_tol=1e-10)
    official_orth = LeaceEraser.fit(xt, st, method='orth', **opts)
    parity = float(np.max(np.abs(official_orth.P.numpy() - p)))
    assert parity < 1e-9, parity
    leace = LeaceEraser.fit(xt, st, method='leace', **opts)
    mu = z_train.mean(0)
    transforms = {'Identity': {'P': np.eye(dim), 'bias': mu},
                  'OPP': {'P': p, 'bias': mu},
                  'LEACE': {'P': leace.P.numpy(), 'bias': leace.bias.numpy()}}
    # INLP intersection-of-nullspaces, fixed three autoregressive rounds.
    # Four joint classes protect both labels without giving either to recipients.
    joint = (2 * sensitive_train[:, 0] + sensitive_train[:, 1]).astype(int)
    rowspaces = []
    current = np.eye(dim)
    iterations = []
    for iteration in range(3):
        classifier = LinearSVC(C=1., class_weight='balanced', max_iter=20000,
                               random_state=20261020)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always')
            classifier.fit(z_train @ current.T, joint)
        w = classifier.coef_
        basis = column_basis(w.T)
        rowspaces.append(basis @ basis.T)
        union = column_basis(np.sum(rowspaces, axis=0))
        current = np.eye(dim) - union @ union.T
        iterations.append({'round': iteration + 1, 'classifier_row_rank': basis.shape[1],
                           'cumulative_removed_rank': union.shape[1],
                           'train_accuracy': float(classifier.score(z_train @ (np.eye(dim) if iteration == 0 else previous).T, joint)),
                           'warnings': [str(x.message) for x in captured]})
        previous = current.copy()
    transforms['INLP3'] = {'P': current, 'bias': np.zeros(dim)}
    return transforms, {'official_orth_max_abs_difference': parity,
                        'U': u.tolist(), 'train_crosscov': cov.tolist(),
                        'INLP3_rounds': iterations,
                        'projection_fit_seconds': time.perf_counter() - start}


def apply_transform(z, transform):
    return (z - transform['bias']) @ transform['P'].T + transform['bias']


def verify(z_train, z_dev, s_train, transforms, fit_meta):
    u = np.asarray(fit_meta['U'])
    out = {}
    for name, t in transforms.items():
        p = t['P']
        tr = apply_transform(z_train, t)
        dv = apply_transform(z_dev, t)
        delta = dv - z_dev
        out[name] = {'rank': int(np.linalg.matrix_rank(p, tol=1e-8)),
                     'symmetry_frobenius': float(np.linalg.norm(p - p.T)),
                     'idempotence_frobenius': float(np.linalg.norm(p @ p - p)),
                     'train_crosscov_frobenius': float(np.linalg.norm(crosscov(tr, s_train))),
                     'dev_vector_changed_rate': float(np.mean(np.linalg.norm(delta, axis=1) > 1e-9)),
                     'dev_mean_L2_change': float(np.linalg.norm(delta, axis=1).mean()),
                     'dev_relative_squared_distortion': float(np.sum(delta**2) / np.sum(z_dev**2))}
    out['OPP'].update({'U_orthonormality_frobenius': float(np.linalg.norm(u.T @ u - np.eye(u.shape[1]))),
                       'sensitive_direction_residual_frobenius': float(np.linalg.norm(transforms['OPP']['P'] @ u))})
    assert out['OPP']['idempotence_frobenius'] < 1e-9
    assert out['OPP']['symmetry_frobenius'] < 1e-9
    assert out['OPP']['sensitive_direction_residual_frobenius'] < 1e-9
    return out
