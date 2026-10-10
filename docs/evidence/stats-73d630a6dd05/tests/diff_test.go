package stats

import (
	"errors"
	"math"
	"testing"
)

type diffTestCase struct {
	name    string
	input   Float64Data
	want    []float64
	wantErr error
}

func diffSlicesApproxEqual(got, want []float64) bool {
	if len(got) != len(want) {
		return false
	}
	const eps = 1e-9
	for i := range got {
		g, w := got[i], want[i]
		switch {
		case math.IsNaN(g) && math.IsNaN(w):
			continue
		case math.IsInf(g, 1) && math.IsInf(w, 1):
			continue
		case math.IsInf(g, -1) && math.IsInf(w, -1):
			continue
		default:
			if math.Abs(g-w) > eps {
				return false
			}
		}
	}
	return true
}

func TestDiff(t *testing.T) {
	cases := []diffTestCase{
		{
			name:    "empty input",
			input:   Float64Data{},
			want:    nil,
			wantErr: ErrEmptyInput,
		},
		{
			name:    "normal input",
			input:   Float64Data{1, 3, 2, 5},
			want:    []float64{2, -1, 3},
			wantErr: nil,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Diff(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil && !diffSlicesApproxEqual(got, tc.want) {
				t.Fatalf("unexpected result: got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestPercentChange(t *testing.T) {
	cases := []diffTestCase{
		{
			name:    "empty input",
			input:   Float64Data{},
			want:    nil,
			wantErr: ErrEmptyInput,
		},
		{
			name:    "normal input",
			input:   Float64Data{1, 3, 2, 5},
			want:    []float64{2, -0.3333333333333333, 1.5},
			wantErr: nil,
		},
		{
			name:    "zero denominator",
			input:   Float64Data{0, 0, 2},
			want:    []float64{math.NaN(), math.Inf(1)},
			wantErr: nil,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PercentChange(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil && !diffSlicesApproxEqual(got, tc.want) {
				t.Fatalf("unexpected result: got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_Diff(t *testing.T) {
	input := Float64Data{10, 7, 9}
	want := []float64{-3, 2}
	got, err := input.Diff()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !diffSlicesApproxEqual(got, want) {
		t.Fatalf("unexpected result: got %v, want %v", got, want)
	}
}

func diffApproxEqual(got, want []float64) bool {
	if len(got) != len(want) {
		return false
	}
	const eps = 1e-9
	for i := range got {
		if math.IsNaN(got[i]) && math.IsNaN(want[i]) {
			continue
		}
		if math.IsInf(got[i], 0) && math.IsInf(want[i], 0) && (got[i] > 0) == (want[i] > 0) {
			continue
		}
		if math.Abs(got[i]-want[i]) > eps {
			return false
		}
	}
	return true
}

func TestFloat64Data_PercentChange(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    []float64
		wantErr bool
	}{
		{"empty", Float64Data{}, nil, true},
		{"single", Float64Data{5}, []float64{}, false},
		{"normal", Float64Data{1, 2, 4}, []float64{1, 1}, false},
		{"zeroPrev", Float64Data{0, 5, 10}, []float64{math.Inf(1), 1}, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.PercentChange()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !diffApproxEqual(got, tc.want) {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}
