package stats

import (
	"errors"
	"math"
	"testing"
)

func regressionApproxEqual(t *testing.T, got, want float64) {
	const eps = 1e-9
	if math.Abs(got-want) > eps {
		t.Fatalf("values differ: got %v want %v", got, want)
	}
}

func regressionComputeLogarithmic(s Series) Series {
	if len(s) == 0 {
		return nil
	}
	logX := make([]float64, len(s))
	referenceLogX := math.Log(s[0].X)
	var sumDeltaLogX, sumY float64
	for i := 0; i < len(s); i++ {
		logX[i] = math.Log(s[i].X)
		sumDeltaLogX += logX[i] - referenceLogX
		sumY += s[i].Y
	}
	meanDeltaLogX := sumDeltaLogX / float64(len(s))
	meanY := sumY / float64(len(s))
	var covariance, variance float64
	for i, coordinate := range s {
		dx := logX[i] - referenceLogX - meanDeltaLogX
		covariance += dx * (coordinate.Y - meanY)
		variance += dx * dx
	}
	a := covariance / variance
	var regressions Series
	for j := 0; j < len(s); j++ {
		regressions = append(regressions, Coordinate{
			X: s[j].X,
			Y: meanY + a*(logX[j]-referenceLogX-meanDeltaLogX),
		})
	}
	return regressions
}

func regressionComputeExponential(s Series) Series {
	if len(s) == 0 {
		return nil
	}
	referenceX := s[0].X
	var sumY, sumDeltaXY, sumYLogY float64
	for i := 0; i < len(s); i++ {
		sumY += s[i].Y
		sumDeltaXY += (s[i].X - referenceX) * s[i].Y
		sumYLogY += s[i].Y * math.Log(s[i].Y)
	}
	meanDeltaX := sumDeltaXY / sumY
	meanLogY := sumYLogY / sumY
	var covariance, variance float64
	for _, coordinate := range s {
		dx := coordinate.X - referenceX - meanDeltaX
		covariance += coordinate.Y * dx * (math.Log(coordinate.Y) - meanLogY)
		variance += coordinate.Y * dx * dx
	}
	b := covariance / variance
	var regressions Series
	for j := 0; j < len(s); j++ {
		regressions = append(regressions, Coordinate{
			X: s[j].X,
			Y: math.Exp(meanLogY + b*(s[j].X-referenceX-meanDeltaX)),
		})
	}
	return regressions
}

func regressionComputeLinear(s Series) Series {
	if len(s) == 0 {
		return nil
	}
	var sumX, sumY float64
	for _, c := range s {
		sumX += c.X
		sumY += c.Y
	}
	meanX := sumX / float64(len(s))
	meanY := sumY / float64(len(s))
	var covariance, variance float64
	for _, c := range s {
		dx := c.X - meanX
		covariance += dx * (c.Y - meanY)
		variance += dx * dx
	}
	gradient := covariance / variance
	var regressions Series
	for _, c := range s {
		regressions = append(regressions, Coordinate{
			X: c.X,
			Y: meanY + gradient*(c.X-meanX),
		})
	}
	return regressions
}

func TestLogarithmicRegression(t *testing.T) {
	cases := []struct {
		name    string
		s       Series
		wantErr error
	}{
		{"empty input", Series{}, EmptyInputErr},
		{"non‑positive X", Series{{X: 0, Y: 1}}, ErrBounds},
		{"variance zero", Series{{X: 2, Y: 1}, {X: 2, Y: 2}}, ErrBounds},
		{"valid series", Series{{X: 1, Y: 2}, {X: 2, Y: 3}, {X: 4, Y: 5}}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := LogarithmicRegression(tc.s)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				if len(got) != len(tc.s) {
					t.Fatalf("result length mismatch: got %d want %d", len(got), len(tc.s))
				}
				expected := regressionComputeLogarithmic(tc.s)
				for i := range got {
					if got[i].X != tc.s[i].X {
						t.Fatalf("X mismatch at %d: got %v want %v", i, got[i].X, tc.s[i].X)
					}
					regressionApproxEqual(t, got[i].Y, expected[i].Y)
				}
			}
		})
	}
}

func TestExponentialRegression(t *testing.T) {
	cases := []struct {
		name    string
		s       Series
		wantErr error
	}{
		{"empty input", Series{}, EmptyInputErr},
		{"non‑positive Y", Series{{X: 1, Y: 0}}, ErrYCoord},
		{"variance zero", Series{{X: 1, Y: 2}, {X: 1, Y: 3}}, ErrBounds},
		{"valid series", Series{{X: 1, Y: 2}, {X: 2, Y: 4}, {X: 3, Y: 8}}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := ExponentialRegression(tc.s)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				if len(got) != len(tc.s) {
					t.Fatalf("result length mismatch: got %d want %d", len(got), len(tc.s))
				}
				expected := regressionComputeExponential(tc.s)
				for i := range got {
					if got[i].X != tc.s[i].X {
						t.Fatalf("X mismatch at %d: got %v want %v", i, got[i].X, tc.s[i].X)
					}
					regressionApproxEqual(t, got[i].Y, expected[i].Y)
				}
			}
		})
	}
}

func TestLinearRegression(t *testing.T) {
	cases := []struct {
		name    string
		s       Series
		wantErr error
	}{
		{"empty input", Series{}, EmptyInputErr},
		{"variance zero", Series{{X: 5, Y: 1}, {X: 5, Y: 2}}, ErrBounds},
		{"valid series", Series{{X: 1, Y: 2}, {X: 2, Y: 3}, {X: 3, Y: 5}}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := LinearRegression(tc.s)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				if len(got) != len(tc.s) {
					t.Fatalf("result length mismatch: got %d want %d", len(got), len(tc.s))
				}
				expected := regressionComputeLinear(tc.s)
				for i := range got {
					if got[i].X != tc.s[i].X {
						t.Fatalf("X mismatch at %d: got %v want %v", i, got[i].X, tc.s[i].X)
					}
					regressionApproxEqual(t, got[i].Y, expected[i].Y)
				}
			}
		})
	}
}

func TestLogarithmicRegression_Uncovered(t *testing.T) {
	cases := []struct {
		name    string
		input   Series
		wantErr error
	}{
		{
			name:    "empty input",
			input:   Series{},
			wantErr: EmptyInputErr,
		},
		{
			name:    "first non‑positive X",
			input:   Series{{X: 0, Y: 1}},
			wantErr: ErrBounds,
		},
		{
			name:    "later non‑positive X",
			input:   Series{{X: 1, Y: 2}, {X: -5, Y: 3}},
			wantErr: ErrBounds,
		},
		{
			name:    "zero variance (all X equal)",
			input:   Series{{X: 1, Y: 2}, {X: 1, Y: 3}},
			wantErr: ErrBounds,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := LogarithmicRegression(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if got != nil {
				t.Errorf("expected nil result on error, got %v", got)
			}
		})
	}
}
