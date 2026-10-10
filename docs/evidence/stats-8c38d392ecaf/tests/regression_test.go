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
	return math.Abs(a-b) <= eps
}

func TestLogarithmicRegression(t *testing.T) {
	cases := []struct {
		name    string
		input   Series
		want    Series
		wantErr error
	}{
		{"empty input", Series{}, nil, EmptyInputErr},
		{"first X non‑positive", Series{{X: 0, Y: 1}}, nil, ErrBounds},
		{"later X non‑positive", Series{{X: 1, Y: 2}, {X: -2, Y: 3}}, nil, ErrBounds},
		{"zero variance (identical X)", Series{{X: 2, Y: 1}, {X: 2, Y: 4}}, nil, ErrBounds},
		{"simple two points", Series{{X: 1, Y: 2}, {X: math.E, Y: 4}}, Series{{X: 1, Y: 2}, {X: math.E, Y: 4}}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := LogarithmicRegression(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if err != nil {
				return
			}
			if len(got) != len(tc.want) {
				t.Fatalf("expected %d points, got %d", len(tc.want), len(got))
			}
			for i := range got {
				if !regressionApproxEqual(got[i].X, tc.want[i].X) || !regressionApproxEqual(got[i].Y, tc.want[i].Y) {
					t.Errorf("point %d: got (%v,%v) want (%v,%v)", i, got[i].X, got[i].Y, tc.want[i].X, tc.want[i].Y)
				}
			}
		})
	}
}

func TestExponentialRegression(t *testing.T) {
	cases := []struct {
		name    string
		input   Series
		want    Series
		wantErr error
	}{
		{"empty input", Series{}, nil, EmptyInputErr},
		{"Y non‑positive", Series{{X: 1, Y: 0}}, nil, ErrYCoord},
		{"zero variance (identical X)", Series{{X: 5, Y: 1}, {X: 5, Y: 2}}, nil, ErrBounds},
		{"simple two points", Series{{X: 0, Y: 1}, {X: 1, Y: math.E}}, Series{{X: 0, Y: 1}, {X: 1, Y: math.E}}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := ExponentialRegression(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if err != nil {
				return
			}
			if len(got) != len(tc.want) {
				t.Fatalf("expected %d points, got %d", len(tc.want), len(got))
			}
			for i := range got {
				if !regressionApproxEqual(got[i].X, tc.want[i].X) || !regressionApproxEqual(got[i].Y, tc.want[i].Y) {
					t.Errorf("point %d: got (%v,%v) want (%v,%v)", i, got[i].X, got[i].Y, tc.want[i].X, tc.want[i].Y)
				}
			}
		})
	}
}

func TestLinearRegression(t *testing.T) {
	cases := []struct {
		name    string
		input   Series
		want    Series
		wantErr error
	}{
		{"empty input", Series{}, nil, EmptyInputErr},
		{"zero variance (identical X)", Series{{X: 3, Y: 1}, {X: 3, Y: 4}}, nil, ErrBounds},
		{"simple two points", Series{{X: 0, Y: 1}, {X: 1, Y: 3}}, Series{{X: 0, Y: 1}, {X: 1, Y: 3}}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := LinearRegression(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if err != nil {
				return
			}
			if len(got) != len(tc.want) {
				t.Fatalf("expected %d points, got %d", len(tc.want), len(got))
			}
			for i := range got {
				if !regressionApproxEqual(got[i].X, tc.want[i].X) || !regressionApproxEqual(got[i].Y, tc.want[i].Y) {
					t.Errorf("point %d: got (%v,%v) want (%v,%v)", i, got[i].X, got[i].Y, tc.want[i].X, tc.want[i].Y)
				}
			}
		})
	}
}
