package stats

import (
	"errors"
	"math"
	"testing"
)

func regressionApproxEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	if math.IsInf(a, 0) || math.IsInf(b, 0) {
		return a == b
	}
	return math.Abs(a-b) <= eps
}

func TestLogarithmicRegression(t *testing.T) {
	cases := []struct {
		name    string
		s       Series
		wantErr error
		check   func(t *testing.T, got Series, orig Series)
	}{
		{
			name:    "empty input",
			s:       Series{},
			wantErr: EmptyInputErr,
		},
		{
			name:    "non-positive first X",
			s:       Series{{X: 0, Y: 1}, {X: 2, Y: 2}},
			wantErr: ErrBounds,
		},
		{
			name:    "identical X values cause ErrBounds",
			s:       Series{{X: 1, Y: 2}, {X: 1, Y: 3}},
			wantErr: ErrBounds,
		},
		{
			name:    "two points regression matches input",
			s:       Series{{X: 1, Y: 2}, {X: math.E, Y: 4}},
			wantErr: nil,
			check: func(t *testing.T, got Series, orig Series) {
				if len(got) != len(orig) {
					t.Fatalf("expected %d points, got %d", len(orig), len(got))
				}
				for i := range got {
					if !regressionApproxEqual(got[i].X, orig[i].X) {
						t.Fatalf("point %d X mismatch: got %v want %v", i, got[i].X, orig[i].X)
					}
					if !regressionApproxEqual(got[i].Y, orig[i].Y) {
						t.Fatalf("point %d Y mismatch: got %v want %v", i, got[i].Y, orig[i].Y)
					}
				}
			},
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := LogarithmicRegression(tc.s)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.check != nil {
				tc.check(t, got, tc.s)
			}
		})
	}
}

func TestExponentialRegression(t *testing.T) {
	cases := []struct {
		name    string
		s       Series
		wantErr error
		check   func(t *testing.T, got Series, orig Series)
	}{
		{
			name:    "empty input",
			s:       Series{},
			wantErr: EmptyInputErr,
		},
		{
			name:    "non-positive Y",
			s:       Series{{X: 1, Y: 0}, {X: 2, Y: 2}},
			wantErr: ErrYCoord,
		},
		{
			name:    "identical X values cause ErrBounds",
			s:       Series{{X: 1, Y: 1}, {X: 1, Y: 2}},
			wantErr: ErrBounds,
		},
		{
			name:    "two points exponential matches input",
			s:       Series{{X: 0, Y: 1}, {X: 1, Y: math.E}},
			wantErr: nil,
			check: func(t *testing.T, got Series, orig Series) {
				if len(got) != len(orig) {
					t.Fatalf("expected %d points, got %d", len(orig), len(got))
				}
				for i := range got {
					if !regressionApproxEqual(got[i].X, orig[i].X) {
						t.Fatalf("point %d X mismatch: got %v want %v", i, got[i].X, orig[i].X)
					}
					if !regressionApproxEqual(got[i].Y, orig[i].Y) {
						t.Fatalf("point %d Y mismatch: got %v want %v", i, got[i].Y, orig[i].Y)
					}
				}
			},
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := ExponentialRegression(tc.s)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.check != nil {
				tc.check(t, got, tc.s)
			}
		})
	}
}

func TestLinearRegression(t *testing.T) {
	cases := []struct {
		name    string
		s       Series
		wantErr error
		check   func(t *testing.T, got Series, orig Series)
	}{
		{
			name:    "empty input",
			s:       Series{},
			wantErr: EmptyInputErr,
		},
		{
			name:    "identical X values cause ErrBounds",
			s:       Series{{X: 1, Y: 2}, {X: 1, Y: 3}},
			wantErr: ErrBounds,
		},
		{
			name:    "two points linear matches input",
			s:       Series{{X: 0, Y: 0}, {X: 1, Y: 1}},
			wantErr: nil,
			check: func(t *testing.T, got Series, orig Series) {
				if len(got) != len(orig) {
					t.Fatalf("expected %d points, got %d", len(orig), len(got))
				}
				for i := range got {
					if !regressionApproxEqual(got[i].X, orig[i].X) {
						t.Fatalf("point %d X mismatch: got %v want %v", i, got[i].X, orig[i].X)
					}
					if !regressionApproxEqual(got[i].Y, orig[i].Y) {
						t.Fatalf("point %d Y mismatch: got %v want %v", i, got[i].Y, orig[i].Y)
					}
				}
			},
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := LinearRegression(tc.s)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.check != nil {
				tc.check(t, got, tc.s)
			}
		})
	}
}

func TestLogarithmicRegression_NonPositiveX(t *testing.T) {
	// First point positive, second point non‑positive triggers ErrBounds inside the loop.
	s := Series{{X: 1, Y: 2}, {X: 0, Y: 3}}
	_, err := LogarithmicRegression(s)
	if err != ErrBounds {
		t.Fatalf("expected ErrBounds, got %v", err)
	}
}

func TestLogarithmicRegression_VarianceZero(t *testing.T) {
	// All X are the same positive value, causing zero variance and ErrBounds.
	s := Series{{X: 2, Y: 1}, {X: 2, Y: 4}, {X: 2, Y: 6}}
	_, err := LogarithmicRegression(s)
	if err != ErrBounds {
		t.Fatalf("expected ErrBounds for zero variance, got %v", err)
	}
}

func TestLogarithmicRegression_Valid(t *testing.T) {
	// Distinct positive X values should produce a regression without error.
	s := Series{{X: 1, Y: 2}, {X: 2, Y: 3}, {X: 4, Y: 5}}
	got, err := LogarithmicRegression(s)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != len(s) {
		t.Fatalf("expected %d results, got %d", len(s), len(got))
	}
	for i, coord := range got {
		if coord.X != s[i].X {
			t.Fatalf("result X mismatch at %d: got %v want %v", i, coord.X, s[i].X)
		}
		if math.IsNaN(coord.Y) || math.IsInf(coord.Y, 0) {
			t.Fatalf("result Y is not a valid number at %d: %v", i, coord.Y)
		}
	}
}
