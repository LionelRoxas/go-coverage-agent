package stats

import (
	"errors"
	"math"
	"testing"
)

func TestPercentile_EdgeCases(t *testing.T) {
	tests := []struct {
		name    string
		input   Float64Data
		percent float64
		want    float64
		wantErr error
		check   func(t *testing.T, got float64)
	}{
		{
			name:    "empty input",
			input:   Float64Data{},
			percent: 50,
			wantErr: EmptyInputErr,
		},
		{
			name:    "invalid percent zero",
			input:   Float64Data{1, 2, 3},
			percent: 0,
			wantErr: BoundsErr,
		},
		{
			name:    "invalid percent over 100",
			input:   Float64Data{1, 2, 3},
			percent: 101,
			wantErr: BoundsErr,
		},
		{
			name:    "single element",
			input:   Float64Data{42},
			percent: 75,
			want:    42,
		},
		{
			name:    "interpolation finite delta",
			input:   Float64Data{4, 1, 3, 2},
			percent: 25,
			want:    1.75,
		},
		{
			name:    "interpolation infinite delta",
			input:   Float64Data{1, math.Inf(1)},
			percent: 50,
			check: func(t *testing.T, got float64) {
				if !math.IsInf(got, 1) {
					t.Fatalf("expected +Inf, got %v", got)
				}
			},
		},
		{
			name:    "exact rank (f=0)",
			input:   Float64Data{3, 1, 2},
			percent: 50,
			want:    2,
		},
		{
			name:    "duplicate values",
			input:   Float64Data{5, 5, 5, 5},
			percent: 30,
			want:    5,
		},
	}
	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Percentile(tc.input, tc.percent)
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
				tc.check(t, got)
				return
			}
			if math.IsNaN(tc.want) {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN, got %v", got)
				}
			} else {
				if math.Abs(got-tc.want) > 1e-9 {
					t.Fatalf("expected %v, got %v", tc.want, got)
				}
			}
		})
	}
}

func TestPercentileNearestRank_EdgeCases(t *testing.T) {
	tests := []struct {
		name    string
		input   Float64Data
		percent float64
		want    float64
		wantErr error
	}{
		{
			name:    "empty input",
			input:   Float64Data{},
			percent: 50,
			wantErr: EmptyInputErr,
		},
		{
			name:    "invalid percent negative",
			input:   Float64Data{1, 2},
			percent: -5,
			wantErr: BoundsErr,
		},
		{
			name:    "invalid percent NaN",
			input:   Float64Data{1, 2},
			percent: math.NaN(),
			wantErr: BoundsErr,
		},
		{
			name:    "percent 100 returns max",
			input:   Float64Data{3, 1, 4, 2},
			percent: 100,
			want:    4,
		},
		{
			name:    "percent 0 returns min",
			input:   Float64Data{3, 1, 4, 2},
			percent: 0,
			want:    1,
		},
		{
			name:    "normal percentile",
			input:   Float64Data{10, 20, 30, 40, 50},
			percent: 40,
			want:    20,
		},
	}
	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PercentileNearestRank(tc.input, tc.percent)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.IsNaN(tc.want) {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN, got %v", got)
				}
			} else {
				if math.Abs(got-tc.want) > 1e-9 {
					t.Fatalf("expected %v, got %v", tc.want, got)
				}
			}
		})
	}
}
