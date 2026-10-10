package stats

import (
	"errors"
	"math"
	"testing"
)

func percentileOfScoreApproxEqual(a, b float64) bool {
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	return math.Abs(a-b) <= 1e-9
}

func TestPercentileOfScore_Empty(t *testing.T) {
	var data Float64Data
	got, err := PercentileOfScore(data, 1.0)
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
	if !math.IsNaN(got) {
		t.Fatalf("expected NaN result, got %v", got)
	}
}

func TestPercentileOfScore_Basic(t *testing.T) {
	cases := []struct {
		name  string
		data  Float64Data
		score float64
		want  float64
	}{
		{
			name:  "score lower than all values",
			data:  Float64Data{10, 20, 30},
			score: 5,
			want:  0,
		},
		{
			name:  "score higher than all values",
			data:  Float64Data{10, 20, 30},
			score: 40,
			want:  100,
		},
		{
			name:  "score equal to all values",
			data:  Float64Data{5, 5, 5, 5},
			score: 5,
			want:  50,
		},
		{
			name:  "mixed values",
			data:  Float64Data{1, 2, 3, 4, 5},
			score: 3,
			want:  50,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PercentileOfScore(tc.data, tc.score)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !percentileOfScoreApproxEqual(got, tc.want) {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_PercentileOfScore(t *testing.T) {
	cases := []struct {
		name  string
		data  Float64Data
		score float64
		want  float64
	}{
		{
			name:  "method forwards correctly",
			data:  Float64Data{1, 2, 3, 4, 5},
			score: 3,
			want:  50,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.PercentileOfScore(tc.score)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !percentileOfScoreApproxEqual(got, tc.want) {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}
