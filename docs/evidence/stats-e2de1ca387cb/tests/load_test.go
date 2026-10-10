package stats

import (
	"math"
	"strings"
	"testing"
	"time"
)

func TestLoadRawData(t *testing.T) {
	const eps = 1e-9
	cases := []struct {
		name  string
		input interface{}
		want  Float64Data
	}{
		{
			name:  "slice of interface mixed",
			input: []interface{}{int(5), uint(6), float64(7.5), "8.2", true, false, time.Duration(9)},
			want:  Float64Data{5, 6, 7.5, 8.2, 1, 0, 9},
		},
		{
			name:  "slice uint",
			input: []uint{1, 2},
			want:  Float64Data{1, 2},
		},
		{
			name:  "slice uint8",
			input: []uint8{3, 4},
			want:  Float64Data{3, 4},
		},
		{
			name:  "slice uint16",
			input: []uint16{5},
			want:  Float64Data{5},
		},
		{
			name:  "slice uint32",
			input: []uint32{6},
			want:  Float64Data{6},
		},
		{
			name:  "slice uint64",
			input: []uint64{7},
			want:  Float64Data{7},
		},
		{
			name:  "slice bool",
			input: []bool{true, false},
			want:  Float64Data{1, 0},
		},
		{
			name:  "slice float64",
			input: []float64{1.1, 2.2},
			want:  Float64Data{1.1, 2.2},
		},
		{
			name:  "slice int",
			input: []int{-1, 2},
			want:  Float64Data{-1, 2},
		},
		{
			name:  "slice int8",
			input: []int8{-3, 4},
			want:  Float64Data{-3, 4},
		},
		{
			name:  "slice int16",
			input: []int16{-5},
			want:  Float64Data{-5},
		},
		{
			name:  "slice int32",
			input: []int32{6},
			want:  Float64Data{6},
		},
		{
			name:  "slice int64",
			input: []int64{-7},
			want:  Float64Data{-7},
		},
		{
			name:  "slice string",
			input: []string{"9.5", "notnum", "10"},
			want:  Float64Data{9.5, 10},
		},
		{
			name:  "slice time.Duration",
			input: []time.Duration{time.Second, 2 * time.Millisecond},
			want:  Float64Data{float64(time.Second), float64(2 * time.Millisecond)},
		},
		{
			name:  "map int int",
			input: map[int]int{0: 3, 1: 4},
			want:  Float64Data{3, 4},
		},
		{
			name:  "map int int8",
			input: map[int]int8{0: 5, 1: 6},
			want:  Float64Data{5, 6},
		},
		{
			name:  "map int int16",
			input: map[int]int16{0: 7, 1: 8},
			want:  Float64Data{7, 8},
		},
		{
			name:  "map int int32",
			input: map[int]int32{0: 9, 1: 10},
			want:  Float64Data{9, 10},
		},
		{
			name:  "map int int64",
			input: map[int]int64{0: 11, 1: 12},
			want:  Float64Data{11, 12},
		},
		{
			name:  "map int string",
			input: map[int]string{0: "13.5", 1: "bad", 2: "14"},
			want:  Float64Data{13.5, 14},
		},
		{
			name:  "map int uint",
			input: map[int]uint{0: 15, 1: 16},
			want:  Float64Data{15, 16},
		},
		{
			name:  "map int uint8",
			input: map[int]uint8{0: 17, 1: 18},
			want:  Float64Data{17, 18},
		},
		{
			name:  "map int uint16",
			input: map[int]uint16{0: 19, 1: 20},
			want:  Float64Data{19, 20},
		},
		{
			name:  "map int uint32",
			input: map[int]uint32{0: 21, 1: 22},
			want:  Float64Data{21, 22},
		},
		{
			name:  "map int uint64",
			input: map[int]uint64{0: 23, 1: 24},
			want:  Float64Data{23, 24},
		},
		{
			name:  "map int bool",
			input: map[int]bool{0: true, 1: false},
			want:  Float64Data{1, 0},
		},
		{
			name:  "map int float64",
			input: map[int]float64{0: 25.5, 1: 26.6},
			want:  Float64Data{25.5, 26.6},
		},
		{
			name:  "map int time.Duration",
			input: map[int]time.Duration{0: time.Second, 1: time.Millisecond},
			want:  Float64Data{float64(time.Second), float64(time.Millisecond)},
		},
		{
			name:  "string input",
			input: "27 28.5 abc",
			want:  Float64Data{27, 28.5},
		},
		{
			name:  "io.Reader input",
			input: strings.NewReader("29 30.5 xyz\n31"),
			want:  Float64Data{29, 30.5, 31},
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := LoadRawData(tc.input)
			if len(got) != len(tc.want) {
				t.Fatalf("len mismatch: got %d want %d", len(got), len(tc.want))
			}
			for i := range got {
				if math.Abs(got[i]-tc.want[i]) > eps {
					t.Fatalf("value mismatch at %d: got %v want %v", i, got[i], tc.want[i])
				}
			}
		})
	}
}
